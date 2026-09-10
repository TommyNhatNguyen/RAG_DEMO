from pathlib import Path

from PIL import Image

from app.processors.ocr import NullOCR, TesseractOCR


def test_null_ocr_returns_empty(tmp_path: Path):
    image = Image.new("RGB", (8, 8), "white")
    path = tmp_path / "blank.png"
    image.save(path)
    assert NullOCR().extract_text(path) == ""


def test_tesseract_engine_is_swappable():
    assert hasattr(TesseractOCR(), "extract_text")
