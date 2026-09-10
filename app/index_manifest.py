from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.ids import nfc
from app.processors.video_checkpoint import DURATION_TOLERANCE, VIDEO_PIPELINE_VERSION


class IndexManifest:
    """Content-hash registry used to skip unchanged files before parse/embed."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, Any] = {"by_hash": {}, "by_path": {}}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self._data = {
            "by_hash": dict(raw.get("by_hash") or {}),
            "by_path": dict(raw.get("by_path") or {}),
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get_by_hash(self, document_id: str) -> dict[str, Any] | None:
        entry = self._data["by_hash"].get(document_id)
        return dict(entry) if entry else None

    def indexed_paths(self) -> list[str]:
        return [nfc(path) for path in self._data["by_path"].keys()]

    def get_hash_for_path(self, relative_path: str) -> str | None:
        return self._data["by_path"].get(nfc(relative_path))

    def is_indexed(self, document_id: str) -> bool:
        return document_id in self._data["by_hash"]

    def is_video_complete(
        self,
        document_id: str,
        target_duration: float,
        version: str = VIDEO_PIPELINE_VERSION,
    ) -> bool:
        entry = self.get_by_hash(document_id)
        if not entry:
            return False
        if entry.get("video_pipeline_version") != version:
            return False
        processed = entry.get("processed_duration")
        if processed is None:
            return False
        return float(processed) + DURATION_TOLERANCE >= float(target_duration)

    def record(
        self,
        document_id: str,
        *,
        relative_path: str,
        filename: str,
        file_type: str,
        content_types: list[str],
        extra: dict[str, Any] | None = None,
    ) -> None:
        relative_path = nfc(relative_path)
        filename = nfc(filename)
        previous_hash = self._data["by_path"].get(relative_path)
        if previous_hash and previous_hash != document_id:
            old = self._data["by_hash"].get(previous_hash)
            if old and old.get("relative_path") == relative_path:
                del self._data["by_hash"][previous_hash]
        entry: dict[str, Any] = {
            "relative_path": relative_path,
            "filename": filename,
            "file_type": file_type,
            "content_types": content_types,
        }
        if extra:
            entry.update(extra)
        self._data["by_hash"][document_id] = entry
        self._data["by_path"][relative_path] = document_id
        self.save()

    def remove_hash(self, document_id: str) -> None:
        entry = self._data["by_hash"].pop(document_id, None)
        if entry:
            path = entry.get("relative_path")
            if path and self._data["by_path"].get(path) == document_id:
                del self._data["by_path"][path]
        self.save()
