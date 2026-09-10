from __future__ import annotations

import logging
from typing import Sequence

from app.config.settings import Settings
from app.models.retrieval import RetrievalResult

logger = logging.getLogger(__name__)

_LECTURE_CUES = (
    "giảng viên",
    "giang vien",
    "buổi",
    "buoi",
    "video",
    "slide",
    "bài giảng",
    "bai giang",
    "timestamp",
    "phút",
    "phut",
    "lectur",
)
_VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v")
_EMPTY_VISUAL_TYPES = {"image", "page", "video_frame"}


def _norm(text: str) -> str:
    return (text or "").casefold()


def is_lecture_query(query: str) -> bool:
    lowered = _norm(query)
    return any(cue in lowered for cue in _LECTURE_CUES)


def is_video_source(source: str | None) -> bool:
    if not source:
        return False
    lowered = _norm(source.replace("\\", "/"))
    return any(lowered.endswith(ext) for ext in _VIDEO_EXTS)


class ScoreReranker:
    def rerank(
        self,
        query: str,
        results: Sequence[RetrievalResult],
        *,
        source: str | None = None,
    ) -> list[RetrievalResult]:
        return sorted(results, key=lambda item: item.score, reverse=True)


class TypePriorReranker(ScoreReranker):
    """Boost lecture transcript/frame types. Not a cross-encoder."""

    def rerank(
        self,
        query: str,
        results: Sequence[RetrievalResult],
        *,
        source: str | None = None,
    ) -> list[RetrievalResult]:
        lecture = is_lecture_query(query) or is_video_source(source)

        def key(item: RetrievalResult) -> float:
            return item.score + self._bonus(item, lecture=lecture)

        return sorted(results, key=key, reverse=True)

    @staticmethod
    def _bonus(item: RetrievalResult, *, lecture: bool) -> float:
        ctype = item.content_type
        if lecture:
            if ctype == "video_segment":
                return 0.02
            if ctype == "video_frame":
                return 0.01
            return 0.0
        if ctype in {"text", "video_segment"}:
            return 0.005
        empty = not (item.content or "").strip()
        if empty and ctype in _EMPTY_VISUAL_TYPES:
            return 0.0
        return 0.0


class Reranker(ScoreReranker):
    """Placeholder protocol implementation. Swap for Qwen3-Reranker later."""


class SequentialReranker(ScoreReranker):
    def __init__(self, *stages: ScoreReranker) -> None:
        self.stages = stages

    def rerank(
        self,
        query: str,
        results: Sequence[RetrievalResult],
        *,
        source: str | None = None,
    ) -> list[RetrievalResult]:
        current = list(results)
        for stage in self.stages:
            current = stage.rerank(query, current, source=source)
        return current


class QwenReranker(ScoreReranker):
    """Lazy-loaded Qwen3 cross-encoder. Default off on 16GB machines."""

    def __init__(
        self,
        model_name: str,
        *,
        device: str = "cpu",
        max_length: int = 512,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.max_length = max_length
        self._tokenizer = None
        self._model = None
        self._failed = False

    def rerank(
        self,
        query: str,
        results: Sequence[RetrievalResult],
        *,
        source: str | None = None,
    ) -> list[RetrievalResult]:
        items = list(results)
        if not items or not self._ensure_loaded():
            return items
        try:
            scores = self._scores(query, [(item.content or "")[:1500] for item in items])
        except Exception:
            logger.exception("Qwen reranker scoring failed; keeping prior order")
            return items
        ranked = sorted(zip(scores, items), key=lambda row: row[0], reverse=True)
        return [item for _, item in ranked]

    def _ensure_loaded(self) -> bool:
        if self._failed:
            return False
        if self._model is not None:
            return True
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            from app.config.settings import resolve_device

            device = resolve_device(self.device)
            tokenizer = AutoTokenizer.from_pretrained(
                self.model_name, trust_remote_code=True, padding_side="left"
            )
            torch_dtype = torch.float16 if device in {"mps", "cuda"} else torch.float32
            try:
                model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    dtype=torch_dtype,
                    trust_remote_code=True,
                    low_cpu_mem_usage=True,
                )
            except TypeError:
                model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    torch_dtype=torch_dtype,
                    trust_remote_code=True,
                    low_cpu_mem_usage=True,
                )
            if device in {"mps", "cuda"}:
                model.to(device)
            model.eval()
            self._tokenizer = tokenizer
            self._model = model
            logger.info("Loaded reranker %s on %s", self.model_name, device)
            return True
        except Exception:
            logger.exception(
                "Failed to load reranker %s; continuing with type-prior only",
                self.model_name,
            )
            self._failed = True
            self._tokenizer = None
            self._model = None
            return False

    def _scores(self, query: str, documents: list[str]) -> list[float]:
        import torch

        tokenizer = self._tokenizer
        model = self._model
        assert tokenizer is not None and model is not None
        instruction = (
            "Given a learner question about an e-learning course, "
            "retrieve relevant course materials that help answer with evidence"
        )
        yes_id = tokenizer.convert_tokens_to_ids("yes")
        no_id = tokenizer.convert_tokens_to_ids("no")
        device = next(model.parameters()).device
        scores: list[float] = []
        for document in documents:
            prompt = (
                f"<Instruct>: {instruction}\n<Query>: {query}\n<Document>: {document}"
            )
            encoded = tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=self.max_length,
            )
            encoded = {key: value.to(device) for key, value in encoded.items()}
            with torch.no_grad():
                logits = model(**encoded).logits[0, -1]
                pair = logits[[no_id, yes_id]]
                prob = torch.softmax(pair.float(), dim=0)[1].item()
            scores.append(float(prob))
        return scores


def build_reranker(settings: Settings) -> ScoreReranker:
    prior = TypePriorReranker()
    if not settings.rerank_enabled:
        return prior
    try:
        return SequentialReranker(
            prior,
            QwenReranker(settings.rerank_model, device=settings.device),
        )
    except Exception:
        logger.exception("Reranker factory failed; using type-prior only")
        return prior
