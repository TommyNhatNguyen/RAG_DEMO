from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from app.models.document import DocumentAsset, TableAsset
from app.models.image import ImageAsset
from app.models.video import VideoAsset, VideoSegment

DOC_EXTS = {".pdf", ".docx", ".pptx", ".ppt"}
TEXT_EXTS = {".txt", ".md", ".markdown"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".tif"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
SKIP_NAMES = {".ds_store", "thumbs.db"}


def detect_kind(path: Path) -> str | None:
    name = path.name.lower()
    if name in SKIP_NAMES or name.startswith("."):
        return None
    suffix = path.suffix.lower()
    if suffix in DOC_EXTS:
        return "document"
    if suffix in TEXT_EXTS:
        return "text"
    if suffix in IMAGE_EXTS:
        return "image"
    if suffix in VIDEO_EXTS:
        return "video"
    return None


def iter_input_files(path: Path) -> list[Path]:
    path = path.expanduser()
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    files: list[Path] = []
    for child in sorted(path.rglob("*")):
        if child.is_file() and detect_kind(child) is not None:
            files.append(child)
    return files


@dataclass
class LoadedDocument:
    asset: DocumentAsset
    text_blocks: list[dict] = field(default_factory=list)
    tables: list[TableAsset] = field(default_factory=list)
    images: list[ImageAsset] = field(default_factory=list)
    page_images: list[ImageAsset] = field(default_factory=list)
    native_text_by_page: dict[int, str] = field(default_factory=dict)


@dataclass
class LoadedVideo:
    asset: VideoAsset
    segments: list[VideoSegment] = field(default_factory=list)
    full_transcript: str = ""


class DocumentLoader(Protocol):
    def load(self, path: Path, document_id: str) -> LoadedDocument: ...
