from pathlib import Path

from app.ids import file_sha256, nfc, relative_posix


def test_unicode_filename_roundtrip(tmp_path: Path):
    folder = tmp_path / "nhapmonbaomatvaanninhmang"
    folder.mkdir()
    path = folder / "Chương 1.pptx"
    path.write_bytes(b"pptx-bytes")
    rel = relative_posix(path, tmp_path)
    assert "Chương" in nfc(rel) or "Chuong" in rel
    assert file_sha256(path) == file_sha256(path)
