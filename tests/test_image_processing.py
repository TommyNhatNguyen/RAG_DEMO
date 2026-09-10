from pathlib import Path

from PIL import Image

from app.processors.image import load_rgb, to_rgb


def test_to_rgb_converts_rgba(tmp_path: Path):
    image = Image.new("RGBA", (4, 4), (10, 20, 30, 128))
    rgb = to_rgb(image)
    assert rgb.mode == "RGB"


def test_load_rgb_from_disk(tmp_path: Path):
    path = tmp_path / "x.png"
    Image.new("L", (4, 4), 128).save(path)
    loaded = load_rgb(path)
    assert loaded.mode == "RGB"
