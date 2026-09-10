from __future__ import annotations

from pathlib import Path

from PIL import Image


def load_rgb(path: Path) -> Image.Image:
    image = Image.open(path)
    return to_rgb(image)


def to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image
    if image.mode in {"RGBA", "LA"}:
        background = Image.new("RGB", image.size, (255, 255, 255))
        alpha = image.split()[-1]
        background.paste(image, mask=alpha)
        return background
    return image.convert("RGB")
