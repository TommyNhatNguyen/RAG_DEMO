from __future__ import annotations

import logging
import time
from typing import Sequence

from app.config.settings import Settings, resolve_device
from app.progress import log_progress

logger = logging.getLogger(__name__)


class VLEmbeddingService:
    """Lazy SentenceTransformer wrapper for Qwen3-VL-Embedding."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer

        device = resolve_device(self.settings.device)
        logger.info("Loading VL embedding model %s on %s", self.settings.vl_embedding_model, device)
        self._model = SentenceTransformer(
            self.settings.vl_embedding_model,
            device=device,
            trust_remote_code=True,
        )

    def embed_images(self, inputs: Sequence[str | dict], batch_size: int | None = None) -> list[list[float]]:
        if not inputs:
            return []
        self._ensure_loaded()
        assert self._model is not None
        size = batch_size or self.settings.vl_batch_size
        total = len(inputs)
        started = time.perf_counter()
        prev = 0
        log_progress(logger, "Embedding frames", 0, total, started=started)
        vectors: list[list[float]] = []
        for start in range(0, total, size):
            batch = list(inputs[start : start + size])
            encoded = self._model.encode(
                batch,
                batch_size=size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            if hasattr(encoded, "tolist"):
                encoded = encoded.tolist()
            if encoded and isinstance(encoded[0], float):
                vectors.append(list(encoded))
            else:
                vectors.extend([list(row) for row in encoded])
            done = min(start + size, total)
            log_progress(logger, "Embedding frames", done, total, started=started, prev=prev)
            prev = done
        return vectors

    def embed_query(self, text: str) -> list[float]:
        self._ensure_loaded()
        assert self._model is not None
        encoded = self._model.encode(
            [text],
            prompt="Retrieve relevant e-learning slides, diagrams, and lecture frames for the query.",
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        if hasattr(encoded, "tolist"):
            encoded = encoded.tolist()
        row = encoded[0]
        return list(row)
