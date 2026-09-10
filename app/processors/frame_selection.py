from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence

from PIL import Image

from app.config.settings import Settings
from app.models.video import VideoSegment


@dataclass
class FrameCandidate:
    timestamp: float
    path: str
    phash: int | None = None
    ocr_text: str = ""
    is_scene_boundary: bool = False
    visual_change: float = 0.0
    metadata: dict = field(default_factory=dict)


class FrameSelectionStrategy(Protocol):
    def select(
        self,
        candidates: list[FrameCandidate],
        segments: list[VideoSegment],
        settings: Settings,
    ) -> dict[str, list[FrameCandidate]]: ...


def average_hash(image: Image.Image, hash_size: int = 8) -> int:
    gray = image.convert("L").resize((hash_size, hash_size), Image.Resampling.BILINEAR)
    pixels = list(gray.getdata())
    avg = sum(pixels) / max(len(pixels), 1)
    bits = 0
    for index, pixel in enumerate(pixels):
        if pixel >= avg:
            bits |= 1 << index
    return bits


def hash_file(path: str, hash_size: int = 8) -> int | None:
    try:
        with Image.open(path) as image:
            return average_hash(image, hash_size)
    except Exception:
        return None


def hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def similarity(left: int, right: int, hash_size: int = 8) -> float:
    bits = hash_size * hash_size
    return 1.0 - hamming(left, right) / bits


def is_near_duplicate(left: int, right: int, threshold: float, hash_size: int = 8) -> bool:
    return similarity(left, right, hash_size) >= threshold


def _ocr_change(current: str, previous: str) -> float:
    a = " ".join((current or "").split()).lower()
    b = " ".join((previous or "").split()).lower()
    if not a and not b:
        return 0.0
    if a != b:
        return 1.0
    return 0.0


def select_representative_frames(
    candidates: Sequence[FrameCandidate],
    segment: VideoSegment,
    settings: Settings,
) -> list[FrameCandidate]:
    """Pick 1–N representative frames for one time window. No embedding model."""
    start, end = segment.start_time, segment.end_time
    window = [c for c in candidates if start <= c.timestamp < end or (c.timestamp == end and end == start)]
    if not window and candidates:
        window = [c for c in candidates if start <= c.timestamp <= end]
    valid = [c for c in window if c.path]
    if not valid:
        return []

    threshold = settings.video_frame_similarity_threshold
    deduped: list[FrameCandidate] = []
    for candidate in valid:
        if candidate.phash is None:
            deduped.append(candidate)
            continue
        if deduped and deduped[-1].phash is not None and is_near_duplicate(
            candidate.phash, deduped[-1].phash, threshold
        ):
            continue
        deduped.append(candidate)
    if not deduped:
        return []

    prev_hash = None
    prev_ocr = ""
    for candidate in deduped:
        if candidate.phash is not None and prev_hash is not None:
            candidate.visual_change = 1.0 - similarity(candidate.phash, prev_hash)
        else:
            candidate.visual_change = 1.0 if prev_hash is None else candidate.visual_change
        candidate.metadata["ocr_change"] = _ocr_change(candidate.ocr_text, prev_ocr)
        if candidate.phash is not None:
            prev_hash = candidate.phash
        if candidate.ocr_text:
            prev_ocr = candidate.ocr_text

    max_frames = max(1, int(settings.video_max_representative_frames))
    duration = max(end - start, 1e-6)
    selected: list[FrameCandidate] = []

    def score(candidate: FrameCandidate) -> float:
        coverage = 1.0
        if selected:
            nearest = min(abs(candidate.timestamp - item.timestamp) for item in selected)
            coverage = min(1.0, nearest / (duration / max(max_frames, 1)))
        return (
            settings.video_visual_change_weight * candidate.visual_change
            + settings.video_ocr_change_weight * float(candidate.metadata.get("ocr_change") or 0.0)
            + settings.video_scene_boundary_weight * (1.0 if candidate.is_scene_boundary else 0.0)
            + settings.video_temporal_coverage_weight * coverage
        )

    remaining = list(deduped)
    while remaining and len(selected) < max_frames:
        remaining.sort(key=score, reverse=True)
        pick = remaining.pop(0)
        selected.append(pick)

    selected.sort(key=lambda item: item.timestamp)
    if not selected and deduped:
        selected = [deduped[len(deduped) // 2]]
    return selected[:max_frames]


class SemanticFrameSelectionStrategy:
    def select(
        self,
        candidates: list[FrameCandidate],
        segments: list[VideoSegment],
        settings: Settings,
    ) -> dict[str, list[FrameCandidate]]:
        chosen: dict[str, list[FrameCandidate]] = {}
        for segment in segments:
            frames = select_representative_frames(candidates, segment, settings)
            if not frames and candidates:
                fallback = [
                    c
                    for c in candidates
                    if segment.start_time <= c.timestamp <= segment.end_time
                ]
                if fallback:
                    step = max(1, len(fallback) // max(1, settings.video_frames_per_segment))
                    frames = fallback[::step][: max(1, settings.video_frames_per_segment)]
            chosen[segment.id] = frames
        return chosen
