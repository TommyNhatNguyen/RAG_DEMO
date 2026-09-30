from pathlib import Path

from app.loaders.base import detect_kind, iter_input_files


def test_detect_supported_kinds(tmp_path: Path):
    assert detect_kind(tmp_path / "a.pdf") == "document"
    assert detect_kind(tmp_path / "a.docx") == "document"
    assert detect_kind(tmp_path / "a.pptx") == "document"
    assert detect_kind(tmp_path / "a.ppt") == "document"
    assert detect_kind(tmp_path / "a.txt") == "text"
    assert detect_kind(tmp_path / "a.md") == "text"
    assert detect_kind(tmp_path / "a.png") == "image"
    assert detect_kind(tmp_path / "a.mp4") == "video"
    assert detect_kind(tmp_path / ".DS_Store") is None
    assert detect_kind(tmp_path / "a.bin") is None


def test_iter_skips_unknown(tmp_path: Path):
    (tmp_path / "keep.md").write_text("# hi")
    (tmp_path / ".DS_Store").write_text("x")
    (tmp_path / "skip.bin").write_text("x")
    files = iter_input_files(tmp_path)
    names = {p.name for p in files}
    assert names == {"keep.md"}
