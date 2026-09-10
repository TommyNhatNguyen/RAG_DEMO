from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from app.processors.image import to_rgb

logger = logging.getLogger(__name__)


def sample_frames(
    video_path: Path,
    dest_dir: Path,
    *,
    start: float,
    end: float,
    count: int,
) -> list[str]:
    import cv2

    dest_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    duration = max(0.0, end - start)
    if count <= 0:
        cap.release()
        return []
    paths: list[str] = []
    for i in range(count):
        if count == 1:
            t = start + duration / 2
        else:
            t = start + (duration * i / (count - 1 if count > 1 else 1))
        t = min(max(t, start), max(end - 0.001, start))
        frame_index = int(t * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = cap.read()
        if not ok:
            continue
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = to_rgb(Image.fromarray(rgb))
        out = dest_dir / f"frame_{i:03d}_{int(t * 1000)}.png"
        image.save(out, format="PNG")
        paths.append(str(out))
    cap.release()
    return paths
