from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from app.processors.ffmpeg_check import FFMPEG_MISSING, require_ffmpeg

logger = logging.getLogger(__name__)


def expected_coarse_count(duration: float, interval: float) -> int:
    if duration <= 0 or interval <= 0:
        return 0
    return max(1, int(duration / interval))


def sample_coarse_frames(
    video_path: Path,
    dest_dir: Path,
    *,
    interval: float,
    max_duration: float | None = None,
    duration: float | None = None,
) -> list[tuple[float, Path]]:
    """Stream 1 frame every `interval` seconds via FFmpeg. Does not load the video into RAM."""
    require_ffmpeg()
    dest_dir.mkdir(parents=True, exist_ok=True)
    for old in dest_dir.glob("candidate_*.jpg"):
        old.unlink()
    fps = 1.0 / interval if interval > 0 else 0.1
    pattern = dest_dir / "candidate_%06d.jpg"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"fps={fps}",
        "-q:v",
        "5",
    ]
    if max_duration is not None and max_duration > 0:
        cmd.extend(["-t", str(max_duration)])
    cmd.append(str(pattern))
    span = max_duration if max_duration is not None and max_duration > 0 else duration
    expected = expected_coarse_count(span, interval) if span else 0
    if expected:
        logger.info(
            "Coarse-sampling frames every %.1fs (expected ~%s) into %s",
            interval,
            expected,
            dest_dir,
        )
    else:
        logger.info("Coarse-sampling frames every %.1fs into %s", interval, dest_dir)
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(FFMPEG_MISSING) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"FFmpeg frame sampling failed: {exc.stderr[-500:] if exc.stderr else exc}") from exc

    frames: list[tuple[float, Path]] = []
    for index, path in enumerate(sorted(dest_dir.glob("candidate_*.jpg"))):
        timestamp = index * interval
        frames.append((timestamp, path))
    logger.info("Coarse candidates: %s", len(frames))
    return frames
