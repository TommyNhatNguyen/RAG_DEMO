from __future__ import annotations

import hashlib
import unicodedata
from pathlib import Path


def nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def vector_id(document_id: str, content_type: str, chunk_index: int) -> str:
    return f"{document_id}:{content_type}:{chunk_index}"


def relative_posix(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return nfc(path.name)
