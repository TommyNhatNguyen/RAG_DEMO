from __future__ import annotations

from pathlib import Path
from typing import Protocol

from PIL import Image


class OCREngine(Protocol):
    def extract_text(self, image: Image.Image | Path) -> str: ...


class TesseractOCR:
    def extract_text(self, image: Image.Image | Path) -> str:
        import pytesseract

        if isinstance(image, Path):
            image = Image.open(image)
        text = pytesseract.image_to_string(image) or ""
        return text.strip()


class NullOCR:
    def extract_text(self, image: Image.Image | Path) -> str:
        return ""
