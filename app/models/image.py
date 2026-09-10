from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ImageAsset(BaseModel):
    id: str
    document_id: str
    path: str
    page_number: int | None = None
    caption: str | None = None
    ocr_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
