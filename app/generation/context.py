from __future__ import annotations

from pathlib import Path

from app.config.settings import Settings
from app.ids import nfc
from app.models.retrieval import RetrievalResult

_EMPTY_CONTEXT = "(Không có ngữ cảnh)"
_EMPTY_SOURCES = "- (không có)"
_EMPTY_VISUAL = "(Không có OCR/caption; đây là ảnh, slide hoặc khung hình được truy xuất theo ngữ nghĩa thị giác.)"
_EMPTY_TEXT = "(Không có nội dung)"
_VISUAL_TYPES = {"image", "page", "video", "video_frame"}


def generation_k(settings: Settings, k: int | None) -> int:
    return k if k is not None else max(settings.retriever_k, settings.generation_k)


def relative_path_for_hit(hit: RetrievalResult) -> str:
    meta = hit.metadata or {}
    rel = (
        meta.get("relative_path")
        or meta.get("filename")
        or meta.get("image_path")
        or meta.get("source")
        or ""
    )
    rel = nfc(str(rel).strip())
    if not rel:
        return "unknown"
    if _looks_absolute(rel):
        return nfc(Path(rel).name)
    return rel


def collect_source_paths(hits: list[RetrievalResult]) -> str:
    paths: list[str] = []
    seen: set[str] = set()
    for hit in hits:
        rel = relative_path_for_hit(hit)
        if rel == "unknown":
            continue
        key = nfc(rel)
        if key in seen:
            continue
        seen.add(key)
        paths.append(f"- {rel}")
    return "\n".join(paths) if paths else _EMPTY_SOURCES


def format_hits(hits: list[RetrievalResult], max_chars: int = 10000) -> str:
    parts: list[str] = []
    total = 0
    for index, hit in enumerate(hits, 1):
        block = _format_block(index, hit)
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block) + 2
    return "\n\n".join(parts) if parts else _EMPTY_CONTEXT


def _format_block(index: int, hit: RetrievalResult) -> str:
    header = _format_header(index, hit)
    body = (hit.content or "").strip()
    if not body:
        if hit.content_type in _VISUAL_TYPES:
            body = _EMPTY_VISUAL
        else:
            body = _EMPTY_TEXT
    return f"{header}\n{body}"


def _format_header(index: int, hit: RetrievalResult) -> str:
    meta = hit.metadata or {}
    loc = relative_path_for_hit(hit)
    page = meta.get("page_number", meta.get("page"))
    if page is not None and page != "":
        loc += f" p.{page}"
    start = meta.get("start_time")
    end = meta.get("end_time")
    if start is not None:
        if end is not None:
            loc += f" @{_fmt_time(start)}-{_fmt_time(end)}s"
        else:
            loc += f" @{_fmt_time(start)}s"
    timestamp = meta.get("timestamp")
    if timestamp is not None and timestamp != "":
        loc += f" t={_fmt_time(timestamp)}s"
    return f"[Đoạn {index} | {hit.content_type} | {loc}]"


def _fmt_time(value: object) -> str:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(value)
    if number == int(number):
        return str(int(number))
    return f"{number:.1f}"


def _looks_absolute(path: str) -> bool:
    if path.startswith("/"):
        return True
    if len(path) > 2 and path[1] == ":":
        return True
    return False
