from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def detect_scene_timestamps(video_path: Path, threshold: float, max_duration: float | None = None) -> list[float]:
    try:
        from scenedetect import SceneManager, open_video
        from scenedetect.detectors import ContentDetector
    except ImportError:
        logger.info("PySceneDetect not installed; skipping scene detection")
        return []

    try:
        video = open_video(str(video_path))
        manager = SceneManager()
        manager.add_detector(ContentDetector(threshold=threshold))
        duration = None
        if max_duration is not None and max_duration > 0:
            from scenedetect.frame_timecode import FrameTimecode

            duration = FrameTimecode(timecode=max_duration, fps=video.frame_rate)
        manager.detect_scenes(video, duration=duration, show_progress=False)
        scenes = manager.get_scene_list()
    except Exception:
        logger.exception("Scene detection failed; continuing without scene boundaries")
        return []

    stamps: list[float] = []
    for start, _end in scenes:
        stamps.append(float(start.get_seconds()))
    logger.info("Scene boundaries: %s", len(stamps))
    return stamps
