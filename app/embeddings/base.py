from __future__ import annotations

from typing import Protocol, Sequence


class TextEmbedder(Protocol):
    def embed_documents(self, texts: Sequence[str], batch_size: int | None = None) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class VLEmbedder(Protocol):
    def embed_images(self, inputs: Sequence[str | dict], batch_size: int | None = None) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...
