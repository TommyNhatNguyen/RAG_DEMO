from __future__ import annotations

import shutil

FFMPEG_MISSING = (
    "FFmpeg is required for long-video processing.\n"
    "Install FFmpeg and ensure it is available on PATH."
)


def require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError(FFMPEG_MISSING)
