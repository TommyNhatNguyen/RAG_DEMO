from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from app.processors.ffmpeg_check import FFMPEG_MISSING, require_ffmpeg

logger = logging.getLogger(__name__)


def extract_audio(
    video_path: Path,
    audio_path: Path,
    max_duration: float | None = None,
    *,
    reuse: bool = True,
) -> Path:
    require_ffmpeg()
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    if reuse and audio_path.exists() and audio_path.stat().st_size > 0:
        logger.info("Reusing extracted audio %s", audio_path.name)
        return audio_path
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
    ]
    if max_duration is not None and max_duration > 0:
        cmd.extend(["-t", str(max_duration)])
    cmd.append(str(audio_path))
    logger.info("Extracting audio with ffmpeg")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(FFMPEG_MISSING) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"FFmpeg audio extraction failed: {exc.stderr[-500:] if exc.stderr else exc}") from exc
    return audio_path
