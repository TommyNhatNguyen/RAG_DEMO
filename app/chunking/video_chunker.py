from __future__ import annotations


def build_time_windows(duration: float, segment_duration: float) -> list[tuple[float, float]]:
    if duration <= 0 or segment_duration <= 0:
        return []
    windows: list[tuple[float, float]] = []
    start = 0.0
    while start < duration:
        end = min(start + segment_duration, duration)
        windows.append((start, end))
        start = end
    return windows


def transcript_for_window(pieces: list[dict], start: float, end: float) -> str:
    """Keep whole Whisper pieces that overlap the window; do not split mid-sentence."""
    texts: list[str] = []
    for piece in pieces:
        p_start = float(piece.get("start") or 0)
        p_end = float(piece.get("end") or p_start)
        if p_end <= start or p_start >= end:
            continue
        text = (piece.get("text") or "").strip()
        if text:
            texts.append(text)
    return " ".join(texts)


def assign_pieces_to_windows(
    pieces: list[dict],
    windows: list[tuple[float, float]],
) -> list[str]:
    """Each Whisper piece belongs to the window that contains its start (full text, no clip)."""
    grouped = [[] for _ in windows]
    for piece in pieces:
        text = (piece.get("text") or "").strip()
        if not text:
            continue
        p_start = float(piece.get("start") or 0)
        placed = False
        for index, (start, end) in enumerate(windows):
            if start <= p_start < end or (index == len(windows) - 1 and p_start <= end):
                grouped[index].append(text)
                placed = True
                break
        if not placed and windows:
            grouped[-1].append(text)
    return [" ".join(parts) for parts in grouped]
