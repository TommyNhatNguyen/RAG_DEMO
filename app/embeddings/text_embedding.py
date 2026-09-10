from __future__ import annotations

import logging
import time
from typing import Sequence

from app.config.settings import Settings, resolve_device
from app.progress import log_progress

logger = logging.getLogger(__name__)

_TEXT_PROGRESS_MIN = 16


class TextEmbeddingService:
    """Lazy HuggingFaceEmbeddings wrapper. Loaded once and reused."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        from langchain_huggingface import HuggingFaceEmbeddings

        device = resolve_device(self.settings.device)
        logger.info("Loading text embedding model %s on %s", self.settings.embedding_model, device)
        self._model = HuggingFaceEmbeddings(
            model_name=self.settings.embedding_model,
            model_kwargs={"device": device, "trust_remote_code": True},
            encode_kwargs={
                "batch_size": self.settings.text_batch_size,
                "normalize_embeddings": True,
            },
            query_encode_kwargs={"normalize_embeddings": True},
            show_progress=False,
        )

    def embed_documents(self, texts: Sequence[str], batch_size: int | None = None) -> list[list[float]]:
        if not texts:
            return []
        self._ensure_loaded()
        assert self._model is not None
        size = batch_size or self.settings.text_batch_size
        total = len(texts)
        verbose = total >= _TEXT_PROGRESS_MIN
        started = time.perf_counter()
        prev = 0
        if verbose:
            log_progress(logger, "Embedding text", 0, total, every=size, started=started)
        vectors: list[list[float]] = []
        for start in range(0, total, size):
            batch = list(texts[start : start + size])
            vectors.extend(self._model.embed_documents(batch))
            if verbose:
                done = min(start + size, total)
                log_progress(
                    logger,
                    "Embedding text",
                    done,
                    total,
                    every=size,
                    started=started,
                    prev=prev,
                )
                prev = done
        return vectors

    def embed_query(self, text: str) -> list[float]:
        self._ensure_loaded()
        assert self._model is not None
        instructed = f"Instruct: {self.settings.query_task}\nQuery:{text}"
        return self._model.embed_query(instructed)
