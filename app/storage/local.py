from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


class LocalFilesystemStore:
    """Store generated images and intermediate assets below one safe root."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, relative_path: str | Path) -> Path:
        candidate = (self.root / Path(relative_path)).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"Storage path escapes root: {relative_path}") from exc
        return candidate

    def put_image(self, relative_path: str | Path, image: Any) -> str:
        """Save a PIL image and return its absolute path."""
        target = self._path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target)
        return str(target)

    def delete_prefix(self, relative_prefix: str | Path) -> None:
        """Delete one generated file or directory below the storage root."""
        target = self._path(relative_prefix)
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
