from __future__ import annotations

from pathlib import Path
from typing import Protocol

from PIL import Image


class ObjectStore(Protocol):
    def put_bytes(self, key: str, data: bytes) -> str: ...

    def put_image(self, key: str, image: Image.Image) -> str: ...

    def put_file(self, key: str, source: Path) -> str: ...

    def delete_prefix(self, prefix: str) -> int: ...
