from app.models.video import VideoSegment
from app.processors.frame_selection import (
    FrameCandidate,
    SemanticFrameSelectionStrategy,
    is_near_duplicate,
    select_representative_frames,
    similarity,
)


def _segment(start: float, end: float, index: int = 0) -> VideoSegment:
    return VideoSegment(
        id=f"vid:video_segment:{index}",
        video_id="vid",
        start_time=start,
        end_time=end,
        transcript="hello",
        metadata={"chunk_index": index},
    )


def _cand(ts: float, phash: int, *, scene: bool = False, ocr: str = "") -> FrameCandidate:
    return FrameCandidate(
        timestamp=ts,
        path=f"/tmp/f{int(ts)}.jpg",
        phash=phash,
        ocr_text=ocr,
        is_scene_boundary=scene,
    )


def test_near_duplicate_and_different():
    same = 0b11110000
    close = 0b11110001
    different = 0b00001111
    assert is_near_duplicate(same, close, 0.90)
    assert not is_near_duplicate(same, different, 0.90)
    assert similarity(same, same) == 1.0


def test_select_removes_duplicates_and_caps():
    segment = _segment(0, 30)
    # First four hashes are near-duplicates; last two are distinct.
    candidates = [
        _cand(1, 0xFF00),
        _cand(2, 0xFF01),
        _cand(3, 0xFF00),
        _cand(15, 0x00FF),
        _cand(27, 0x0F0F),
        _cand(28, 0x0F0E),
    ]
    from app.config.settings import Settings

    settings = Settings(video_max_representative_frames=3, video_frame_similarity_threshold=0.90)
    chosen = select_representative_frames(candidates, segment, settings)
    assert len(chosen) <= 3
    stamps = [c.timestamp for c in chosen]
    assert stamps == sorted(stamps)
    assert max(stamps) - min(stamps) >= 10


def test_temporal_coverage_not_all_at_start():
    segment = _segment(0, 30)
    candidates = [
        _cand(0, 0x0000000000000000),
        _cand(10, 0xFFFFFFFFFFFFFFFF),
        _cand(20, 0x00FF00FF00FF00FF),
        _cand(28, 0xF0F0F0F0F0F0F0F0),
    ]
    from app.config.settings import Settings

    settings = Settings(video_max_representative_frames=3)
    chosen = select_representative_frames(candidates, segment, settings)
    assert len(chosen) == 3
    stamps = [c.timestamp for c in chosen]
    assert max(stamps) - min(stamps) > 5


def test_high_scoring_scene_and_ocr_preferred(settings):
    segment = _segment(0, 30)
    candidates = [
        _cand(5, 0x1111, ocr="intro"),
        _cand(15, 0xEEEE, scene=True, ocr="B-tree index"),
        _cand(25, 0x1110, ocr="intro"),
    ]
    chosen = select_representative_frames(candidates, segment, settings)
    assert any(c.timestamp == 15 for c in chosen)


def test_strategy_maps_segments(settings):
    segments = [_segment(0, 30, 0), _segment(30, 60, 1)]
    candidates = [
        _cand(10, 0xAAAA),
        _cand(40, 0x5555),
        _cand(50, 0x00FF),
    ]
    mapping = SemanticFrameSelectionStrategy().select(candidates, segments, settings)
    assert segments[0].id in mapping
    assert mapping[segments[0].id]
    assert mapping[segments[1].id]
