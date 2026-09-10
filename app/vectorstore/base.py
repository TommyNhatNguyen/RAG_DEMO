from __future__ import annotations

from typing import Any, Protocol, Sequence


class VectorStore(Protocol):
    def add(
        self,
        collection: str,
        ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        documents: Sequence[str | None],
        metadatas: Sequence[dict[str, Any]],
    ) -> tuple[int, int]:
        """Return (added, skipped)."""

    def search(
        self,
        collection: str,
        query_embedding: Sequence[float],
        k: int,
    ) -> list[dict[str, Any]]: ...

    def delete(self, collection: str, ids: Sequence[str] | None = None, where: dict[str, Any] | None = None) -> int: ...

    def get(self, collection: str, ids: Sequence[str] | None = None, where: dict[str, Any] | None = None) -> dict[str, Any]: ...

    def count(self, collection: str) -> int: ...

    def has_document(self, collection: str, document_id: str) -> bool: ...
