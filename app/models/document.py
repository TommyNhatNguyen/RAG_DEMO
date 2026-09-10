from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DocumentAsset(BaseModel):
    id: str
    source: str
    file_name: str
    relative_path: str
    file_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TableAsset(BaseModel):
    id: str
    document_id: str
    page_number: int | None = None
    section: str | None = None
    rows: int | None = None
    columns: int | None = None
    markdown: str
    image_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
