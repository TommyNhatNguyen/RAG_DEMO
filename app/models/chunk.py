from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TextChunk(BaseModel):
    id: str
    document_id: str
    text: str
    page_number: int | None = None
    section: str | None = None
    chunk_index: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmbeddingRecord(BaseModel):
    id: str
    document_id: str
    collection: str
    content_type: str
    content: str | None = None
    embedding: list[float]
    metadata: dict[str, Any] = Field(default_factory=dict)
