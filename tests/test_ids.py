from pathlib import Path

from app.ids import file_sha256, nfc, relative_posix, vector_id


def test_vector_id_format():
    assert vector_id("abc123", "text", 0) == "abc123:text:0"


def test_file_hash_is_content_not_path(tmp_path: Path):
    a = tmp_path / "one.txt"
    b = tmp_path / "Chương 1.txt"
    a.write_bytes(b"hello")
    b.write_bytes(b"hello")
    assert file_sha256(a) == file_sha256(b)


def test_hash_changes_with_content(tmp_path: Path):
    path = tmp_path / "doc.txt"
    path.write_bytes(b"hello")
    first = file_sha256(path)
    path.write_bytes(b"hello!")
    assert file_sha256(path) != first


def test_nfc_vietnamese():
    nfd = "Chuong\u0301 1.pptx"
    assert nfc(nfd) == "Chương 1.pptx" or "\u0301" not in nfc(nfd)


def test_relative_posix(tmp_path: Path):
    nested = tmp_path / "assets" / "test" / "file.txt"
    nested.parent.mkdir(parents=True)
    nested.write_text("x")
    assert relative_posix(nested, tmp_path) == "assets/test/file.txt"
