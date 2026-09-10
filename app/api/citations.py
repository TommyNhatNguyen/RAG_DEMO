from __future__ import annotations

import mimetypes
from pathlib import Path

from app.api.schemas import Asset, AssetKind, Citation, Locator
from app.config.settings import Settings
from app.generation.context import relative_path_for_hit
from app.ids import nfc
from app.models.retrieval import RetrievalResult

_VIDEO_TYPES = {"video", "video_segment", "video_frame"}
_IMAGE_TYPES = {"image"}
_VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".tif"}
_SLIDE_SUFFIXES = {".pptx", ".ppt"}
_PDF_SUFFIXES = {".pdf"}
_SNIPPET_LEN = 240


def hits_to_citations_and_assets(
    hits: list[RetrievalResult],
    *,
    settings: Settings | None = None,
) -> tuple[list[Citation], list[Asset]]:
    citations: list[Citation] = []
    assets_by_id: dict[str, Asset] = {}
    storage = settings.resolve_path(settings.storage_root) if settings else None

    for index, hit in enumerate(hits, 1):
        rel = relative_path_for_hit(hit)
        asset_id = nfc(rel)
        meta = hit.metadata or {}
        filename = nfc(str(meta.get("filename") or meta.get("file_name") or Path(rel).name))
        locator = _locator_from_meta(meta)
        kind = _kind(hit.content_type, rel, str(meta.get("file_type") or ""))
        file_url = _file_url(rel)
        preview = _preview_url(meta.get("image_path"), storage)
        citations.append(
            Citation(
                id=hit.id,
                index=index,
                content_type=hit.content_type,
                score=float(hit.score),
                title=filename,
                snippet=_snippet(hit.content),
                locator=locator,
                asset_id=asset_id,
            )
        )
        existing = assets_by_id.get(asset_id)
        if existing is None:
            watch = _watch_url(file_url, kind, locator, preview)
            assets_by_id[asset_id] = Asset(
                id=asset_id,
                kind=kind,
                filename=filename,
                media_type=_media_type(filename, kind),
                download_url=file_url,
                watch_url=watch,
                preview_url=preview,
                locators=_unique_locators([locator]),
            )
        else:
            existing.locators = _unique_locators([*existing.locators, locator])
            if existing.preview_url is None and preview:
                existing.preview_url = preview
            if existing.watch_url == existing.download_url:
                existing.watch_url = _watch_url(file_url, kind, locator, preview)

    return citations, list(assets_by_id.values())


def _kind(content_type: str, relative_path: str, file_type: str) -> AssetKind:
    suffix = Path(relative_path).suffix.lower()
    file_type = (file_type or "").lower().lstrip(".")
    if content_type in _VIDEO_TYPES or suffix in _VIDEO_SUFFIXES or file_type in {
        "mp4",
        "mov",
        "mkv",
        "avi",
        "webm",
        "m4v",
    }:
        return "video"
    if suffix in _PDF_SUFFIXES or file_type == "pdf":
        return "pdf"
    if suffix in _SLIDE_SUFFIXES or file_type in {"pptx", "ppt"}:
        return "slide"
    if content_type in _IMAGE_TYPES or suffix in _IMAGE_SUFFIXES:
        return "image"
    if content_type == "page":
        if suffix in _PDF_SUFFIXES:
            return "pdf"
        if suffix in _SLIDE_SUFFIXES:
            return "slide"
        return "image"
    return "document"


def _file_url(relative_path: str) -> str:
    rel = relative_path.replace("\\", "/").lstrip("/")
    return f"/v1/files/{rel}"


def _preview_url(image_path: object, storage: Path | None) -> str | None:
    if not image_path or storage is None:
        return None
    raw = Path(str(image_path))
    try:
        resolved = raw.resolve()
        rel = resolved.relative_to(storage.resolve())
    except (OSError, ValueError):
        text = str(image_path).replace("\\", "/")
        marker = "/storage/"
        idx = text.find(marker)
        if idx == -1:
            return None
        return f"/v1/files/storage/{text[idx + len(marker):]}"
    return f"/v1/files/storage/{rel.as_posix()}"


def _locator_from_meta(meta: dict) -> Locator:
    page = meta.get("page_number", meta.get("page"))
    page_i = None
    if page is not None and page != "":
        try:
            page_i = int(page)
        except (TypeError, ValueError):
            page_i = None
    start = _float_or_none(meta.get("start_time"))
    end = _float_or_none(meta.get("end_time"))
    timestamp = _float_or_none(meta.get("timestamp"))
    return Locator(
        page=page_i,
        start_time=start,
        end_time=end,
        timestamp=timestamp,
        label=_locator_label(page_i, start, end, timestamp),
    )


def _watch_url(file_url: str, kind: AssetKind, locator: Locator, preview: str | None) -> str:
    if kind == "video":
        start = locator.start_time if locator.start_time is not None else locator.timestamp
        if start is not None:
            start_s = _frag_time(start)
            if locator.end_time is not None:
                return f"{file_url}#t={start_s},{_frag_time(locator.end_time)}"
            return f"{file_url}#t={start_s}"
        return file_url
    if kind == "pdf" and locator.page is not None:
        return f"{file_url}#page={locator.page}"
    if kind == "slide" and preview:
        return preview
    return file_url


def _locator_label(
    page: int | None,
    start: float | None,
    end: float | None,
    timestamp: float | None,
) -> str | None:
    parts: list[str] = []
    if page is not None:
        parts.append(f"p.{page}")
    if start is not None:
        if end is not None:
            parts.append(f"{_clock(start)}–{_clock(end)}")
        else:
            parts.append(_clock(start))
    elif timestamp is not None:
        parts.append(_clock(timestamp))
    return " ".join(parts) if parts else None


def _unique_locators(items: list[Locator]) -> list[Locator]:
    seen: set[tuple] = set()
    out: list[Locator] = []
    for item in items:
        if item.page is None and item.start_time is None and item.end_time is None and item.timestamp is None:
            continue
        key = (item.page, item.start_time, item.end_time, item.timestamp)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _snippet(content: str | None) -> str:
    text = " ".join((content or "").split())
    if len(text) <= _SNIPPET_LEN:
        return text
    return text[: _SNIPPET_LEN - 1] + "…"


def _media_type(filename: str, kind: AssetKind) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    if guessed:
        return guessed
    if kind == "video":
        return "video/mp4"
    if kind == "pdf":
        return "application/pdf"
    if kind == "image":
        return "image/jpeg"
    if kind == "slide":
        return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    return "application/octet-stream"


def _float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _frag_time(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}"


def _clock(value: float) -> str:
    total = int(round(value))
    minutes, seconds = divmod(max(total, 0), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
