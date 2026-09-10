from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Sequence

import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)

ALLOWED_META = (str, int, float, bool)


def flatten_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, ALLOWED_META):
            cleaned[str(key)] = value
        else:
            cleaned[str(key)] = str(value)
    return cleaned


class ChromaVectorStore:
    def __init__(self, persist_path: Path, text_collection: str, visual_collection: str) -> None:
        persist_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(persist_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.text_collection = text_collection
        self.visual_collection = visual_collection
        self._collections: dict[str, Any] = {}
        self._collection(text_collection)
        self._collection(visual_collection)

    def _collection(self, name: str):
        if name not in self._collections:
            self._collections[name] = self._client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[name]

    def add(
        self,
        collection: str,
        ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        documents: Sequence[str | None],
        metadatas: Sequence[dict[str, Any]],
    ) -> tuple[int, int]:
        if not ids:
            return 0, 0
        coll = self._collection(collection)
        existing = set(self._existing_ids(coll, list(ids)))
        pending_ids: list[str] = []
        pending_emb: list[list[float]] = []
        pending_docs: list[str] = []
        pending_meta: list[dict[str, Any]] = []
        for vec_id, embedding, document, metadata in zip(ids, embeddings, documents, metadatas):
            if vec_id in existing:
                continue
            pending_ids.append(vec_id)
            pending_emb.append(list(embedding))
            pending_docs.append(document if document is not None else "")
            pending_meta.append(flatten_metadata(metadata))
        skipped = len(ids) - len(pending_ids)
        if pending_ids:
            coll.add(
                ids=pending_ids,
                embeddings=pending_emb,
                documents=pending_docs,
                metadatas=pending_meta,
            )
        logger.info("Chroma %s add: added=%s skipped=%s", collection, len(pending_ids), skipped)
        return len(pending_ids), skipped

    def _existing_ids(self, coll, ids: list[str]) -> list[str]:
        if not ids:
            return []
        found: list[str] = []
        chunk_size = 100
        for start in range(0, len(ids), chunk_size):
            chunk = ids[start : start + chunk_size]
            got = coll.get(ids=chunk, include=[])
            found.extend(got.get("ids") or [])
        return found

    def search(
        self,
        collection: str,
        query_embedding: Sequence[float],
        k: int,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        coll = self._collection(collection)
        if coll.count() == 0:
            return []
        n = min(k, coll.count())
        kwargs: dict[str, Any] = {
            "query_embeddings": [list(query_embedding)],
            "n_results": n,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        try:
            result = coll.query(**kwargs)
        except Exception:
            logger.exception("Chroma query failed collection=%s where=%s", collection, where)
            return []
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        hits: list[dict[str, Any]] = []
        for vec_id, document, metadata, distance in zip(ids, docs, metas, distances):
            distance_f = float(distance)
            hits.append(
                {
                    "id": vec_id,
                    "document": document,
                    "metadata": metadata or {},
                    "distance": distance_f,
                    "score": 1.0 - distance_f,
                }
            )
        return hits

    def delete(
        self,
        collection: str,
        ids: Sequence[str] | None = None,
        where: dict[str, Any] | None = None,
    ) -> int:
        coll = self._collection(collection)
        before = coll.count()
        if ids:
            existing = self._existing_ids(coll, list(ids))
            if existing:
                coll.delete(ids=existing)
        elif where:
            coll.delete(where=where)
        else:
            return 0
        return max(0, before - coll.count())

    def get(
        self,
        collection: str,
        ids: Sequence[str] | None = None,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        coll = self._collection(collection)
        kwargs: dict[str, Any] = {"include": ["documents", "metadatas"]}
        if ids is not None:
            kwargs["ids"] = list(ids)
        if where is not None:
            kwargs["where"] = where
        return coll.get(**kwargs)

    def count(self, collection: str) -> int:
        return self._collection(collection).count()

    def has_document(self, collection: str, document_id: str) -> bool:
        got = self.get(collection, where={"document_id": document_id})
        return bool(got.get("ids"))
