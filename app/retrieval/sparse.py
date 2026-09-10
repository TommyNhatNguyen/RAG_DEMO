from __future__ import annotations

import logging
import pickle
import re
from pathlib import Path
from typing import Any

from app.models.retrieval import RetrievalResult

logger = logging.getLogger(__name__)

_TEXT_TYPES = {"text", "table", "video_segment", "ocr"}
_TOKEN = re.compile(r"\W+", flags=re.UNICODE)


def tokenize_query(text: str) -> list[str]:
    from app.retrieval.retriever import process_user_query

    cleaned = process_user_query(text).casefold()
    return [token for token in _TOKEN.split(cleaned) if token]


class BM25Index:
    def __init__(self) -> None:
        self.ids: list[str] = []
        self.documents: list[str] = []
        self.metadatas: list[dict[str, Any]] = []
        self._bm25: Any = None

    @property
    def size(self) -> int:
        return len(self.ids)

    def search(self, query: str, k: int) -> list[RetrievalResult]:
        tokens = tokenize_query(query)
        if not tokens or self._bm25 is None or not self.ids:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda row: row[1], reverse=True)
        out: list[RetrievalResult] = []
        for index, score in ranked[: max(0, k)]:
            if float(score) <= 0:
                continue
            meta = dict(self.metadatas[index] or {})
            out.append(
                RetrievalResult(
                    id=self.ids[index],
                    score=float(score),
                    content_type=str(meta.get("content_type") or "text"),
                    content=self.documents[index],
                    metadata=meta,
                )
            )
        return out

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ids": self.ids,
            "documents": self.documents,
            "metadatas": self.metadatas,
            "tokenized": [tokenize_query(doc) for doc in self.documents],
        }
        path.write_bytes(pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL))

    @classmethod
    def load(cls, path: Path) -> BM25Index | None:
        if not path.exists():
            return None
        try:
            payload = pickle.loads(path.read_bytes())
        except Exception:
            logger.exception("Failed to load BM25 index %s", path)
            return None
        index = cls()
        index.ids = list(payload.get("ids") or [])
        index.documents = list(payload.get("documents") or [])
        index.metadatas = list(payload.get("metadatas") or [])
        tokenized = payload.get("tokenized") or [
            tokenize_query(doc) for doc in index.documents
        ]
        index._bm25 = _make_bm25(tokenized)
        return index if index._bm25 is not None else None


def rebuild_bm25(vector_store: Any, collection: str) -> BM25Index:
    got = vector_store.get(collection)
    ids = got.get("ids") or []
    docs = got.get("documents") or []
    metas = got.get("metadatas") or []
    index = BM25Index()
    tokenized: list[list[str]] = []
    for vec_id, document, metadata in zip(ids, docs, metas):
        meta = dict(metadata or {})
        ctype = str(meta.get("content_type") or "text")
        if ctype not in _TEXT_TYPES:
            continue
        text = (document or "").strip()
        if not text:
            continue
        index.ids.append(vec_id)
        index.documents.append(text)
        index.metadatas.append(meta)
        tokenized.append(tokenize_query(text))
    index._bm25 = _make_bm25(tokenized)
    return index


def persist_bm25(vector_store: Any, collection: str, path: Path) -> BM25Index:
    index = rebuild_bm25(vector_store, collection)
    index.save(path)
    logger.info("BM25 rebuilt docs=%s path=%s", index.size, path)
    return index


def _make_bm25(tokenized: list[list[str]]) -> Any | None:
    if not tokenized:
        return None
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        logger.warning('BM25 extra missing. Install with: pip install -e ".[retrieval]"')
        return None
    corpus = [row or [""] for row in tokenized]
    return BM25Okapi(corpus)
