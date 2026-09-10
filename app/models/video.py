from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VideoAsset(BaseModel):
    id: str
    source: str
    file_name: str
    relative_path: str
    duration: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class VideoSegment(BaseModel):
    id: str
    video_id: str
    start_time: float
    end_time: float
    transcript: str = ""
    frame_paths: list[str] = Field(default_factory=list)
    frame_timestamps: list[float] = Field(default_factory=list)
    ocr_texts: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
