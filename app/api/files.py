from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse

from app.api.deps import get_settings
from app.config.settings import Settings

router = APIRouter()


def resolve_public_file(settings: Settings, url_path: str) -> Path:
    raw = (url_path or "").replace("\\", "/").lstrip("/")
    if not raw or raw.startswith("/") or ".." in Path(raw).parts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    parts = Path(raw).parts
    root = Path(parts[0])
    rest = Path(*parts[1:]) if len(parts) > 1 else Path()
    if root.name == "assets":
        base = (settings.project_root / "assets").resolve()
    elif root.name == "storage":
        base = settings.resolve_path(settings.storage_root).resolve()
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        full = (base / rest).resolve()
        full.relative_to(base)
    except (OSError, ValueError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    if not full.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return full


@router.get("/v1/files/{path:path}")
def serve_file(path: str, request: Request) -> FileResponse:
    settings: Settings = get_settings(request)
    full = resolve_public_file(settings, path)
    media_type, _ = mimetypes.guess_type(full.name)
    return FileResponse(
        full,
        media_type=media_type or "application/octet-stream",
        content_disposition_type="inline",
    )
