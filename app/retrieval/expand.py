from __future__ import annotations

from typing import Any

from app.models.retrieval import RetrievalResult
from app.retrieval.filters import combine_where
from app.vectorstore.chroma import ChromaVectorStore

_PAGE_TYPES = {"text", "table"}
_VIDEO_TYPES = {"video_segment"}


def expand_hits(
    results: list[RetrievalResult],
    vector_store: ChromaVectorStore,
    collection: str,
) -> list[RetrievalResult]:
    seen_pages: set[tuple[str, Any]] = set()
    seen_windows: set[tuple[str, int]] = set()
    out: list[RetrievalResult] = []
    for item in results:
        meta = item.metadata or {}
        document_id = str(meta.get("document_id") or "")
        ctype = item.content_type
        page = meta.get("page_number", meta.get("page"))
        chunk_index = meta.get("chunk_index")
        if ctype in _PAGE_TYPES and document_id and page not in (None, ""):
            key = (document_id, page)
            if key in seen_pages:
                continue
            seen_pages.add(key)
            parent = _join_siblings(
                vector_store,
                collection,
                combine_where({"document_id": document_id}, {"page_number": page}),
            )
            out.append(item.model_copy(update={"content": parent or item.content}))
            continue
        if ctype in _VIDEO_TYPES | _PAGE_TYPES and document_id and chunk_index is not None:
            try:
                index = int(chunk_index)
            except (TypeError, ValueError):
                out.append(item)
                continue
            key = (document_id, index)
            if key in seen_windows:
                continue
            seen_windows.add(key)
            parent = _join_neighbors(vector_store, collection, document_id, index)
            out.append(item.model_copy(update={"content": parent or item.content}))
            continue
        out.append(item)
    return out


def _join_siblings(
    vector_store: ChromaVectorStore,
    collection: str,
    where: dict[str, Any] | None,
) -> str:
    got = vector_store.get(collection, where=where)
    return _sorted_join(got)


def _join_neighbors(
    vector_store: ChromaVectorStore,
    collection: str,
    document_id: str,
    chunk_index: int,
) -> str:
    parts: list[str] = []
    for neighbor in (chunk_index - 1, chunk_index, chunk_index + 1):
        got = vector_store.get(
            collection,
            where=combine_where({"document_id": document_id}, {"chunk_index": neighbor}),
        )
        text = _sorted_join(got)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _sorted_join(got: dict[str, Any]) -> str:
    ids = got.get("ids") or []
    docs = got.get("documents") or []
    metas = got.get("metadatas") or []
    rows: list[tuple[int, str]] = []
    for vec_id, document, metadata in zip(ids, docs, metas):
        meta = metadata or {}
        try:
            order = int(meta.get("chunk_index") if meta.get("chunk_index") is not None else 0)
        except (TypeError, ValueError):
            order = 0
        text = (document or "").strip()
        if text:
            rows.append((order, text))
        del vec_id
    rows.sort(key=lambda row: row[0])
    return "\n".join(text for _, text in rows)
