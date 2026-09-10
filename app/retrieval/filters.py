from __future__ import annotations

from typing import Any

_FILE_EXTS = (
    ".pdf",
    ".docx",
    ".pptx",
    ".ppt",
    ".txt",
    ".md",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".m4v",
)


def combine_where(*parts: dict[str, Any] | None) -> dict[str, Any] | None:
    clauses = [part for part in parts if part]
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def is_file_source(source: str) -> bool:
    lowered = source.replace("\\", "/").lower()
    return any(lowered.endswith(ext) for ext in _FILE_EXTS)


def normalize_source(source: str | None) -> str:
    return (source or "").strip().replace("\\", "/").lstrip("./")


def source_clause(source: str | None) -> dict[str, Any] | None:
    text = normalize_source(source)
    if not text or not is_file_source(text):
        return None
    if "/" in text or text.startswith("assets"):
        return {"relative_path": text}
    return {"filename": text}


def folder_prefix(source: str | None) -> str | None:
    text = normalize_source(source)
    if not text or is_file_source(text):
        return None
    if text.startswith("assets/") or "/" in text:
        return text.rstrip("/")
    return f"assets/{text}"


def chroma_where(
    source: str | None = None,
    course: str | None = None,
    content_type: str | None = None,
) -> dict[str, Any] | None:
    return combine_where(
        source_clause(source),
        {"course": course} if course else None,
        {"content_type": content_type} if content_type else None,
    )


def matches_prefix(relative_path: str, prefix: str) -> bool:
    rel = (relative_path or "").replace("\\", "/").lstrip("./")
    prefix = prefix.rstrip("/")
    return rel == prefix or rel.startswith(prefix + "/")


def matches_course(relative_path: str, course: str, meta_course: str | None = None) -> bool:
    if course and meta_course == course:
        return True
    rel = (relative_path or "").replace("\\", "/")
    token = course.strip("/")
    return f"/{token}/" in f"/{rel}/" or rel.startswith(f"assets/{token}/")
