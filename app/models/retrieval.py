from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ContentType = Literal[
    "text",
    "image",
    "table",
    "video",
    "video_segment",
    "video_frame",
    "page",
]


class RetrievalResult(BaseModel):
    id: str
    score: float
    content_type: str
    content: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
