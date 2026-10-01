from __future__ import annotations

import gc
import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, NamedTuple

from app.config.settings import Settings, resolve_device
from app.generation.catalog import is_catalog_query, match_manifest_paths, merge_source_paths
from app.generation.context import format_hits, generation_k
from app.generation.prompts import build_answer_prompt
from app.generation.query_enhance import (
    EnhancedQuery,
    build_enhance_prompt,
    build_hyde_prompt,
    build_reflect_prompt,
    parse_enhanced_query,
    parse_hyde_paragraph,
    parse_reflect_decision,
)
from app.generation.think import ThinkStreamFilter, strip_think
from app.index_manifest import IndexManifest
from app.models.retrieval import RetrievalResult
from app.retrieval.retriever import MultimodalRetriever, process_user_query

logger = logging.getLogger(__name__)


def _stdout_printer(text: str) -> None:
    print(text, end="", flush=True)


_MISSING_EXTRA = (
    'LLM generation requires extra "generation". '
    'Install with: pip install -e ".[generation]" or pip install -e ".[all]"'
)


_FALLBACK_ANSWER = (
    "Không đủ học liệu khớp câu hỏi với độ tin cậy đủ. "
    "Không tạo lộ trình bịa, không bịa URL hay liên kết markdown.\n\n"
    "Tài liệu gốc đã biết:\n{source_paths}"
)


def _merge_hits_by_id(
    primary: list[RetrievalResult], extra: list[RetrievalResult]
) -> list[RetrievalResult]:
    by_id: dict[str, RetrievalResult] = {}
    for hit in [*primary, *extra]:
        prev = by_id.get(hit.id)
        if prev is None or hit.score > prev.score:
            by_id[hit.id] = hit
    return sorted(by_id.values(), key=lambda item: item.score, reverse=True)


def _max_cosine(hits: list[RetrievalResult]) -> float:
    values: list[float] = []
    for hit in hits:
        value = (hit.metadata or {}).get("cosine")
        if value is None:
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    if values:
        return max(values)
    return 1.0 if hits else 0.0


class AskEvent(NamedTuple):
    name: str
    data: dict[str, Any]


class GenerationService:
    def __init__(
        self,
        settings: Settings,
        retriever: MultimodalRetriever,
        chat_model: Any | None = None,
        manifest: IndexManifest | None = None,
        vl_answerer: Any | None = None,
    ) -> None:
        self.settings = settings
        self.retriever = retriever
        self.manifest = manifest
        self._chat = chat_model
        self._injected = chat_model is not None
        self._vl_answerer = vl_answerer
        self._vl_injected = vl_answerer is not None
        self.last_hits: list[RetrievalResult] = []
        self.last_enhanced: EnhancedQuery | None = None
        self.last_retrieve_loops: int = 0

    def generate(
        self,
        query: str,
        *,
        k: int | None = None,
        include_visual: bool = True,
        enhance: bool | None = None,
        source: str | None = None,
        course: str | None = None,
        content_type: str | None = None,
    ) -> str:
        return self.generate_answer(
            query,
            k=k,
            include_visual=include_visual,
            enhance=enhance,
            source=source,
            course=course,
            content_type=content_type,
        )

    def stream(
        self,
        query: str,
        *,
        k: int | None = None,
        include_visual: bool = True,
        enhance: bool | None = None,
        source: str | None = None,
        course: str | None = None,
        content_type: str | None = None,
    ) -> Iterator[str]:
        return self.iter_answer_tokens(
            query,
            k=k,
            include_visual=include_visual,
            enhance=enhance,
            source=source,
            course=course,
            content_type=content_type,
        )

    def generate_answer(
        self,
        raw_query: str,
        *,
        k: int | None = None,
        include_visual: bool = True,
        enhance: bool | None = None,
        source: str | None = None,
        course: str | None = None,
        content_type: str | None = None,
    ) -> str:
        question, context, source_paths, fallback = self._prepare(
            raw_query,
            k=k,
            include_visual=include_visual,
            enhance=enhance,
            source=source,
            course=course,
            content_type=content_type,
        )
        if fallback:
            return fallback
        if include_visual and self._document_visual_hits(self.last_hits):
            raw = self._invoke_visual(question)
        else:
            raw = self._invoke(
                {"context": context, "question": question, "source_paths": source_paths}
            )
        return strip_think(raw)

    def generate_answer_stream(
        self,
        raw_query: str,
        *,
        k: int | None = None,
        include_visual: bool = True,
        enhance: bool | None = None,
        source: str | None = None,
        course: str | None = None,
        content_type: str | None = None,
        printer: Callable[[str], None] | None = None,
    ) -> str:
        if printer is None:
            printer = _stdout_printer
        parts: list[str] = []
        for token in self.iter_answer_tokens(
            raw_query,
            k=k,
            include_visual=include_visual,
            enhance=enhance,
            source=source,
            course=course,
            content_type=content_type,
        ):
            printer(token)
            parts.append(token)
        return strip_think("".join(parts))

    def iter_answer_tokens(
        self,
        raw_query: str,
        *,
        k: int | None = None,
        include_visual: bool = True,
        enhance: bool | None = None,
        source: str | None = None,
        course: str | None = None,
        content_type: str | None = None,
    ) -> Iterator[str]:
        for event in self.iter_ask_events(
            raw_query,
            k=k,
            include_visual=include_visual,
            enhance=enhance,
            source=source,
            course=course,
            content_type=content_type,
        ):
            if event.name == "delta":
                yield str(event.data.get("text") or "")

    def iter_ask_events(
        self,
        raw_query: str,
        *,
        k: int | None = None,
        include_visual: bool = True,
        enhance: bool | None = None,
        source: str | None = None,
        course: str | None = None,
        content_type: str | None = None,
    ) -> Iterator[AskEvent]:
        question, context, source_paths, fallback, enhanced = self._retrieve(
            raw_query,
            k=k,
            include_visual=include_visual,
            enhance=enhance,
            source=source,
            course=course,
            content_type=content_type,
            emit_status=True,
        )
        if enhanced is not None:
            yield AskEvent("status", {"stage": "enhancing"})
            yield AskEvent(
                "query",
                {
                    "rewritten": enhanced.rewritten,
                    "subqueries": list(enhanced.subqueries),
                    "step_back": enhanced.step_back or "",
                    "hyde": enhanced.hyde or "",
                },
            )
        yield AskEvent("status", {"stage": "retrieving"})
        for _ in range(max(0, self.last_retrieve_loops)):
            yield AskEvent("status", {"stage": "retrieving"})
        yield AskEvent("sources", {})
        if fallback:
            yield AskEvent("status", {"stage": "generating"})
            yield AskEvent("delta", {"text": fallback})
            yield AskEvent("done", {})
            return
        yield AskEvent("status", {"stage": "generating"})
        if include_visual and self._document_visual_hits(self.last_hits):
            answer = strip_think(self._invoke_visual(question))
            if answer:
                yield AskEvent("delta", {"text": answer})
            yield AskEvent("done", {})
            return
        filt = ThinkStreamFilter()
        for chunk in self._stream(
            {"context": context, "question": question, "source_paths": source_paths}
        ):
            text = chunk if isinstance(chunk, str) else getattr(chunk, "content", "") or ""
            visible = filt.feed(text)
            if visible:
                yield AskEvent("delta", {"text": visible})
        tail = filt.flush()
        if tail:
            yield AskEvent("delta", {"text": tail})
        yield AskEvent("done", {})

    def _prepare(
        self,
        raw_query: str,
        *,
        k: int | None,
        include_visual: bool,
        enhance: bool | None = None,
        source: str | None = None,
        course: str | None = None,
        content_type: str | None = None,
    ) -> tuple[str, str, str, str | None]:
        question, context, source_paths, fallback, _enhanced = self._retrieve(
            raw_query,
            k=k,
            include_visual=include_visual,
            enhance=enhance,
            source=source,
            course=course,
            content_type=content_type,
            emit_status=False,
        )
        return question, context, source_paths, fallback

    def retrieve_for_eval(
        self,
        raw_query: str,
        *,
        k: int | None = None,
        include_visual: bool = True,
        enhance: bool | None = None,
        source: str | None = None,
        course: str | None = None,
        content_type: str | None = None,
    ) -> list[RetrievalResult]:
        """Run the real query-enhance/HyDE/iterative-loop retrieval path and
        return just the hits, for benchmark harnesses that want to measure
        the full generation-time retrieval pipeline (not only bare
        `retriever.search()`)."""
        self._retrieve(
            raw_query,
            k=k,
            include_visual=include_visual,
            enhance=enhance,
            source=source,
            course=course,
            content_type=content_type,
            emit_status=False,
        )
        return self.last_hits

    def _retrieve(
        self,
        raw_query: str,
        *,
        k: int | None,
        include_visual: bool,
        enhance: bool | None,
        source: str | None,
        course: str | None,
        content_type: str | None,
        emit_status: bool,
    ) -> tuple[str, str, str, str | None, EnhancedQuery | None]:
        del emit_status
        question = process_user_query(raw_query)
        if not question:
            raise ValueError("Empty query after processing.")
        k = generation_k(self.settings, k)
        do_enhance = self.settings.query_enhance if enhance is None else enhance
        self.last_enhanced = None
        self.last_retrieve_loops = 0
        search_query = question
        enhanced: EnhancedQuery | None = None
        if do_enhance:
            enhanced = self._enhance_query(question)
            logger.info(
                "Query enhance rewritten=%s subqueries=%s step_back=%s",
                enhanced.rewritten,
                enhanced.subqueries,
                enhanced.step_back or "",
            )
            search_query = enhanced.original
        if self.settings.query_hyde:
            if enhanced is None:
                enhanced = EnhancedQuery.identity(question)
            hyde = self._hyde_paragraph(question)
            if hyde:
                enhanced.hyde = hyde
                logger.info("HyDE paragraph chars=%s", len(hyde))
        if enhanced is not None:
            self.last_enhanced = enhanced
        hits = self.retriever.search(
            search_query,
            k=k,
            include_visual=include_visual,
            enhanced=enhanced,
            source=source,
            course=course,
            content_type=content_type,
        )
        extra_paths = (
            match_manifest_paths(self.manifest, question)
            if is_catalog_query(question)
            else []
        )
        hits, context, source_paths = self._maybe_retrieve_loop(
            question,
            hits,
            extra_paths,
            k=k,
            include_visual=include_visual,
            source=source,
            course=course,
            content_type=content_type,
        )
        self.last_hits = hits
        fallback = self._fallback_answer(hits, source_paths)
        return question, context, source_paths, fallback, enhanced

    def _fallback_answer(
        self, hits: list[RetrievalResult], source_paths: str
    ) -> str | None:
        if not hits or _max_cosine(hits) < self.settings.cosine_fallback_threshold:
            return _FALLBACK_ANSWER.format(source_paths=source_paths)
        return None

    def _enhance_query(self, cleaned: str) -> EnhancedQuery:
        try:
            raw = self._invoke_enhancer(cleaned)
        except Exception:
            logger.exception("Query enhance LLM call failed; using original question")
            return EnhancedQuery.identity(cleaned)
        parsed = parse_enhanced_query(
            raw,
            cleaned,
            max_subqueries=self.settings.query_enhance_max_subqueries,
        )
        return parsed

    def _hyde_paragraph(self, question: str) -> str:
        try:
            raw = self._invoke_hyde(question)
        except Exception:
            logger.exception("HyDE LLM call failed; skipping HyDE")
            return ""
        return parse_hyde_paragraph(raw)

    def _maybe_retrieve_loop(
        self,
        question: str,
        hits: list[RetrievalResult],
        extra_paths: list[str],
        *,
        k: int,
        include_visual: bool,
        source: str | None,
        course: str | None,
        content_type: str | None,
    ) -> tuple[list[RetrievalResult], str, str]:
        context = format_hits(hits, max_chars=self.settings.llm_max_context_chars)
        source_paths = merge_source_paths(hits, extra_paths)
        max_loops = min(1, max(0, int(self.settings.max_retrieve_loops or 0)))
        while self.last_retrieve_loops < max_loops:
            decision = self._reflect_need_more(question, context, source_paths)
            follow_up = process_user_query(str(decision.get("follow_up") or ""))
            if not decision.get("needs_more") or not follow_up:
                break
            extra = self.retriever.search(
                follow_up,
                k=k,
                include_visual=include_visual,
                source=source,
                course=course,
                content_type=content_type,
            )
            hits = _merge_hits_by_id(hits, extra)[:k]
            context = format_hits(hits, max_chars=self.settings.llm_max_context_chars)
            source_paths = merge_source_paths(hits, extra_paths)
            self.last_retrieve_loops += 1
        return hits, context, source_paths

    def _reflect_need_more(
        self, question: str, context: str, source_paths: str
    ) -> dict[str, object]:
        try:
            raw = self._invoke_reflect(question, context, source_paths)
        except Exception:
            logger.exception("Retrieve-loop reflect failed; stopping")
            return {"needs_more": False, "follow_up": ""}
        return parse_reflect_decision(raw)

    def _invoke_hyde(self, question: str) -> str:
        if self._injected:
            result = self._chat.invoke({"question": question, "hyde": True})
            return self._as_text(result)
        self._ensure_loaded()
        messages = build_hyde_prompt().format_messages(question=question)
        return self._invoke_with_short_tokens(messages)

    def _invoke_reflect(self, question: str, context: str, source_paths: str) -> str:
        if self._injected:
            result = self._chat.invoke(
                {
                    "question": question,
                    "context": context,
                    "source_paths": source_paths,
                    "reflect": True,
                }
            )
            return self._as_text(result)
        self._ensure_loaded()
        messages = build_reflect_prompt().format_messages(
            question=question,
            context=context[:4000],
            source_paths=source_paths,
        )
        return self._invoke_with_short_tokens(messages)

    def _invoke_enhancer(self, cleaned: str) -> str:
        if self._injected:
            result = self._chat.invoke({"question": cleaned, "enhance": True})
            return self._as_text(result)
        self._ensure_loaded()
        messages = build_enhance_prompt().format_messages(question=cleaned)
        return self._invoke_with_short_tokens(messages)

    def _invoke_with_short_tokens(self, messages: Any) -> str:
        cfg = self._model_generation_config()
        previous = None
        if cfg is not None:
            previous = cfg.max_new_tokens
            cfg.max_new_tokens = self.settings.query_enhance_max_new_tokens
        try:
            result = self._chat.invoke(messages)
        finally:
            if cfg is not None and previous is not None:
                cfg.max_new_tokens = previous
        return self._as_text(result)

    def _model_generation_config(self) -> Any:
        llm = getattr(self._chat, "llm", None)
        pipe = getattr(llm, "pipeline", None)
        model = getattr(pipe, "model", None)
        return getattr(model, "generation_config", None)

    @staticmethod
    def _document_visual_hits(
        hits: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """Return retrieved page/picture assets usable by Qwen-VL."""
        valid: list[RetrievalResult] = []
        for hit in hits:
            if hit.content_type not in {"page", "image"}:
                continue
            metadata = hit.metadata or {}
            file_type = str(metadata.get("file_type") or "").lower().lstrip(".")
            relative = str(metadata.get("relative_path") or "")
            if not file_type:
                file_type = Path(relative).suffix.lower().lstrip(".")
            if file_type not in {"pdf", "ppt", "pptx", "docx"}:
                continue
            image_path = Path(str(metadata.get("image_path") or ""))
            if image_path.is_file():
                valid.append(hit)
        return valid

    def _ensure_vl_loaded(self) -> Any:
        if self._vl_answerer is not None:
            return self._vl_answerer
        self._release_text_model()
        from app.generation.vl_answerer import LocalQwenVLAnswerer

        self._vl_answerer = LocalQwenVLAnswerer(
            model_name=self.settings.vl_llm_model,
            device=self.settings.device,
            max_new_tokens=self.settings.vl_llm_max_new_tokens,
        )
        return self._vl_answerer

    def _invoke_visual(self, question: str) -> str:
        answerer = self._ensure_vl_loaded()
        return answerer.answer(
            question,
            self.last_hits,
            max_images=self.settings.vl_max_images,
        )

    def _release_text_model(self) -> None:
        if self._injected or self._chat is None:
            return
        self._chat = None
        gc.collect()
        try:
            import torch

            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
        except (ImportError, AttributeError):
            pass

    def _release_vl_model(self) -> None:
        if self._vl_injected or self._vl_answerer is None:
            return
        answerer = self._vl_answerer
        self._vl_answerer = None
        close = getattr(answerer, "close", None)
        if callable(close):
            close()
        else:
            del answerer
            gc.collect()

    @staticmethod
    def _as_text(result: Any) -> str:
        if isinstance(result, str):
            return result
        return str(getattr(result, "content", result) or "")

    def _ensure_loaded(self) -> None:
        if self._chat is not None:
            return
        self._release_vl_model()
        try:
            import torch
            from langchain_huggingface import ChatHuggingFace, HuggingFacePipeline
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from transformers import pipeline as hf_pipeline
        except ImportError as exc:
            raise RuntimeError(_MISSING_EXTRA) from exc

        device = resolve_device(self.settings.device)
        if device == "cpu":
            torch_dtype = torch.float32
            logger.warning("No GPU/MPS — LLM on CPU will be slow.")
        else:
            torch_dtype = torch.float16

        model_name = self.settings.llm_model
        max_new = self.settings.llm_max_new_tokens
        thinking = self.settings.llm_enable_thinking
        do_sample = self.settings.llm_do_sample
        logger.info(
            "Loading %s on %s (thinking=%s, max_new_tokens=%s)",
            model_name,
            device,
            thinking,
            max_new,
        )

        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        original_apply = tokenizer.apply_chat_template

        def _apply_chat_template(*args, **kwargs):
            kwargs["enable_thinking"] = thinking
            return original_apply(*args, **kwargs)

        tokenizer.apply_chat_template = _apply_chat_template

        pretrained_kwargs: dict[str, Any] = {
            "trust_remote_code": True,
            "low_cpu_mem_usage": True,
        }
        try:
            model = AutoModelForCausalLM.from_pretrained(
                model_name, dtype=torch_dtype, **pretrained_kwargs
            )
        except TypeError:
            model = AutoModelForCausalLM.from_pretrained(
                model_name, torch_dtype=torch_dtype, **pretrained_kwargs
            )
        if device in {"mps", "cuda"}:
            model.to(device)

        if getattr(model, "generation_config", None) is not None:
            model.generation_config.max_new_tokens = max_new
            model.generation_config.do_sample = do_sample
            model.generation_config.max_length = None

        pipe_kwargs: dict[str, Any] = {
            "task": "text-generation",
            "model": model,
            "tokenizer": tokenizer,
            "return_full_text": False,
        }
        if device == "cpu":
            pipe_kwargs["device"] = -1

        pipe = hf_pipeline(**pipe_kwargs)
        self._chat = ChatHuggingFace(
            llm=HuggingFacePipeline(pipeline=pipe),
            tokenizer=tokenizer,
        )
        logger.info(
            "LLM ready: %s on %s thinking=%s MAX_NEW_TOKENS=%s",
            model_name,
            device,
            thinking,
            max_new,
        )

    def _real_chain(self):
        from langchain_core.output_parsers import StrOutputParser

        self._ensure_loaded()
        return build_answer_prompt() | self._chat | StrOutputParser()

    def _invoke(self, payload: dict[str, str]) -> str:
        self._release_vl_model()
        if self._injected:
            result = self._chat.invoke(payload)
            return result if isinstance(result, str) else str(getattr(result, "content", result))
        return self._real_chain().invoke(payload)

    def _stream(self, payload: dict[str, str]) -> Iterator[str]:
        self._release_vl_model()
        if self._injected:
            yield from self._chat.stream(payload)
            return
        yield from self._real_chain().stream(payload)
