from app.chunking.video_chunker import assign_pieces_to_windows, build_time_windows, transcript_for_window
from app.processors.ffmpeg_check import FFMPEG_MISSING, require_ffmpeg
import pytest


def test_time_windows():
    windows = build_time_windows(40, 15)
    assert windows == [(0, 15), (15, 30), (30, 40)]


def test_time_windows_four_hours():
    windows = build_time_windows(14400, 30)
    assert len(windows) == 480
    assert windows[0] == (0, 30)
    assert windows[-1] == (14370, 14400)


def test_transcript_overlap():
    pieces = [
        {"start": 0, "end": 10, "text": "hello"},
        {"start": 14, "end": 20, "text": "world"},
        {"start": 40, "end": 50, "text": "later"},
    ]
    assert transcript_for_window(pieces, 0, 15) == "hello world"
    assert transcript_for_window(pieces, 30, 45) == "later"


def test_assign_pieces_keeps_full_sentence():
    windows = [(0, 30), (30, 60)]
    pieces = [
        {"start": 28, "end": 36, "text": "a B-tree index works by splitting nodes"},
        {"start": 40, "end": 44, "text": "next topic"},
    ]
    grouped = assign_pieces_to_windows(pieces, windows)
    assert "B-tree index works by splitting nodes" in grouped[0]
    assert "B-tree" not in grouped[1]
    assert grouped[1] == "next topic"


def test_require_ffmpeg_missing(monkeypatch):
    monkeypatch.setattr("app.processors.ffmpeg_check.shutil.which", lambda _name: None)
    with pytest.raises(RuntimeError, match="FFmpeg is required"):
        require_ffmpeg()
    assert "PATH" in FFMPEG_MISSING
