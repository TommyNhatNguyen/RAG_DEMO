from __future__ import annotations

import json
import logging
from typing import Any

from app.generation.query_enhance import _extract_json_object
from app.generation.think import strip_think

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """Bạn là giám khảo RAG cho trợ lý e-learning. Chỉ dùng ngữ cảnh và đáp án vàng.

Chấm điểm từ 0 đến 1:
- faithfulness: mọi khẳng định trong câu trả lời có trong ngữ cảnh (không bịa).
- answer_relevancy: câu trả lời đúng trọng tâm câu hỏi.
- context_precision: các đoạn ngữ cảnh có liên quan đến câu hỏi / đáp án vàng.
- context_recall: ngữ cảnh có đủ ý của đáp án vàng.

completeness: thang 1-5 (đủ ý cho người học).

Chỉ JSON, không markdown:
{{"faithfulness":0.0,"answer_relevancy":0.0,"context_precision":0.0,"context_recall":0.0,"completeness":1}}

Câu hỏi: {question}

Đáp án vàng: {reference}

Ngữ cảnh:
{contexts}

Câu trả lời:
{answer}

JSON:"""


def score_with_judge(chat: Any, *, question: str, reference: str, contexts: list[str], answer: str) -> dict[str, float]:
    payload = JUDGE_PROMPT.format(
        question=question,
        reference=reference or "(không có)",
        contexts="\n---\n".join(contexts)[:8000] or "(trống)",
        answer=answer or "(trống)",
    )
    raw = chat.invoke({"question": payload, "judge": True})
    text = raw if isinstance(raw, str) else str(getattr(raw, "content", raw) or "")
    return parse_judge_scores(text)


def parse_judge_scores(raw: str) -> dict[str, float]:
    blob = _extract_json_object(strip_think(raw or "")) or ""
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        logger.warning("Judge: invalid JSON")
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, float] = {}
    for key in ("faithfulness", "answer_relevancy", "context_precision", "context_recall"):
        try:
            out[key] = max(0.0, min(1.0, float(data[key])))
        except (KeyError, TypeError, ValueError):
            continue
    try:
        completeness = float(data.get("completeness"))
        out["completeness"] = max(1.0, min(5.0, completeness))
    except (TypeError, ValueError):
        pass
    return out
