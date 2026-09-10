from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from langchain_core.prompts import ChatPromptTemplate

from app.generation.catalog import catalog_subqueries, is_catalog_query
from app.generation.think import strip_think
from app.retrieval.retriever import process_user_query

logger = logging.getLogger(__name__)

ENHANCE_SYSTEM = """Bạn là bộ lập kế hoạch truy vấn cho trợ lý ảo e-learning dùng RAG đa phương thức (văn bản, slide, bảng, công thức, transcript, video).

Nhiệm vụ: chuẩn hóa câu hỏi người học thành truy vấn tìm kiếm trên học liệu khóa học. Sửa chính tả, bỏ từ đệm, map cách nói đời thường sang thuật ngữ giáo trình. Giữ tín hiệu môn học, chương, tuần, chủ đề nếu có trong câu hỏi.

Chỉ trả về JSON hợp lệ, không markdown, không giải thích:
{{"rewritten":"...","subqueries":[],"step_back":""}}

Quy tắc:
- rewritten: một câu hỏi rõ, độc lập, đủ nghĩa để embed và search trên học liệu e-learning.
- subqueries: tối đa 3 câu, chỉ khi câu gốc gồm nhiều phần độc lập (ví dụ lý thuyết + bài tập + mốc thời gian video). Nếu không thì [].
- step_back: một câu hỏi khái niệm / mục tiêu học tập rộng hơn. Nếu không cần thì "".
- Không bịa đề bài, không bịa nội dung bài giảng. Không viết câu trả lời giả (không HyDE)."""

ENHANCE_HUMAN = """Câu hỏi của người học:
{question}

JSON:"""

HYDE_SYSTEM = """Bạn viết một đoạn văn ngắn (3–5 câu) mô tả chủ đề học liệu e-learning liên quan câu hỏi người học, để dùng làm truy vấn tìm kiếm (HyDE).

Quy tắc:
- Chỉ mô tả khái niệm / mục lục / loại tài liệu có thể tồn tại trong giáo trình.
- Không giải bài, không viết đáp án đầy đủ, không bịa đề bài hay bài tập.
- Không viết URL. Tiếng Việt. Không JSON, không markdown."""

HYDE_HUMAN = """Câu hỏi: {question}

Đoạn văn:"""


@dataclass
class EnhancedQuery:
    original: str
    rewritten: str
    subqueries: list[str] = field(default_factory=list)
    step_back: str | None = None
    hyde: str | None = None

    @classmethod
    def identity(cls, cleaned: str) -> EnhancedQuery:
        return cls(original=cleaned, rewritten=cleaned, subqueries=[], step_back=None, hyde=None)

    def text_search_queries(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        extras = (
            catalog_subqueries(self.original)
            if is_catalog_query(self.original) and not self.subqueries
            else []
        )
        for item in [self.original, self.rewritten, *self.subqueries, *extras, self.step_back or ""]:
            text = process_user_query(item or "")
            key = text.casefold()
            if not text or key in seen:
                continue
            seen.add(key)
            out.append(text)
        return out or [self.original]


def build_enhance_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", ENHANCE_SYSTEM),
            ("human", ENHANCE_HUMAN),
        ]
    )


def parse_enhanced_query(
    raw: str,
    original: str,
    *,
    max_subqueries: int = 3,
) -> EnhancedQuery:
    fallback = EnhancedQuery.identity(original)
    text = strip_think(raw or "")
    blob = _extract_json_object(text)
    if not blob:
        logger.warning(
            "Query enhance: no JSON in model output; using original question"
        )
        return fallback
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        logger.warning("Query enhance: invalid JSON; using original question")
        return fallback
    if not isinstance(data, dict):
        return fallback

    rewritten = process_user_query(str(data.get("rewritten") or original))
    if not rewritten:
        rewritten = original

    subqueries_raw = data.get("subqueries") or []
    if not isinstance(subqueries_raw, list):
        subqueries_raw = []
    subqueries: list[str] = []
    seen = {rewritten.casefold()}
    for item in subqueries_raw:
        text_item = process_user_query(str(item or ""))
        if not text_item or text_item.casefold() in seen:
            continue
        seen.add(text_item.casefold())
        subqueries.append(text_item)
        if len(subqueries) >= max(0, max_subqueries):
            break

    step_raw = data.get("step_back")
    if step_raw is None:
        step_raw = ""
    step_back = process_user_query(str(step_raw))
    if (
        not step_back
        or step_back.casefold() in seen
        or step_back.casefold() == original.casefold()
    ):
        step_back_out: str | None = None
    else:
        step_back_out = step_back

    if is_catalog_query(original) and not subqueries:
        fillers = catalog_subqueries(original)
        for item in fillers:
            text_item = process_user_query(item)
            if not text_item or text_item.casefold() in seen:
                continue
            seen.add(text_item.casefold())
            subqueries.append(text_item)
            if len(subqueries) >= max(0, max_subqueries):
                break

    return EnhancedQuery(
        original=original,
        rewritten=rewritten,
        subqueries=subqueries,
        step_back=step_back_out,
    )


def build_hyde_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", HYDE_SYSTEM),
            ("human", HYDE_HUMAN),
        ]
    )


def parse_hyde_paragraph(raw: str) -> str:
    text = process_user_query(strip_think(raw or ""))
    if not text:
        return ""
    return text[:800]


REFLECT_SYSTEM = """Bạn quyết định có cần retrieve thêm học liệu hay không. Chỉ JSON, không markdown:
{{"needs_more":false,"follow_up":""}}

Quy tắc:
- needs_more=true chỉ khi ngữ cảnh thiếu ý quan trọng của câu hỏi.
- follow_up: một câu truy vấn ngắn trên học liệu (không giải bài, không bịa đề bài).
- Nếu đủ thì needs_more=false và follow_up=""."""

REFLECT_HUMAN = """Câu hỏi: {question}

Nguồn: {source_paths}

Ngữ cảnh:
{context}

JSON:"""


def build_reflect_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", REFLECT_SYSTEM),
            ("human", REFLECT_HUMAN),
        ]
    )


def parse_reflect_decision(raw: str) -> dict[str, object]:
    blob = _extract_json_object(strip_think(raw or "")) or ""
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return {"needs_more": False, "follow_up": ""}
    if not isinstance(data, dict):
        return {"needs_more": False, "follow_up": ""}
    needs = data.get("needs_more")
    if isinstance(needs, str):
        needs_more = needs.strip().lower() in {"1", "true", "yes", "có"}
    else:
        needs_more = bool(needs)
    follow_up = process_user_query(str(data.get("follow_up") or ""))[:200]
    if not needs_more:
        follow_up = ""
    return {"needs_more": needs_more, "follow_up": follow_up}


def _extract_json_object(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    return text[start : end + 1]
