from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.processors.ffmpeg_check import FFMPEG_MISSING, require_ffmpeg

logger = logging.getLogger(__name__)


@dataclass
class VideoMetadata:
    duration_seconds: float
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    has_audio: bool = False


def probe_video(video_path: Path) -> VideoMetadata:
    require_ffmpeg()
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=index,codec_type,width,height,r_frame_rate",
                "-of",
                "json",
                str(video_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(FFMPEG_MISSING) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ffprobe failed for {video_path}: {exc.stderr}") from exc

    payload = json.loads(result.stdout or "{}")
    duration = float((payload.get("format") or {}).get("duration") or 0)
    width = height = None
    fps = None
    has_audio = False
    for stream in payload.get("streams") or []:
        kind = stream.get("codec_type")
        if kind == "audio":
            has_audio = True
        if kind == "video" and width is None:
            width = int(stream["width"]) if stream.get("width") else None
            height = int(stream["height"]) if stream.get("height") else None
            fps = _parse_fps(stream.get("r_frame_rate"))
    return VideoMetadata(
        duration_seconds=duration,
        width=width,
        height=height,
        fps=fps,
        has_audio=has_audio,
    )


def probe_duration(video_path: Path) -> float:
    return probe_video(video_path).duration_seconds


def _parse_fps(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" in value:
        num, den = value.split("/", 1)
        try:
            denom = float(den)
            if denom == 0:
                return None
            return float(num) / denom
        except ValueError:
            return None
    try:
        return float(value)
    except ValueError:
        return None
