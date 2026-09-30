from pathlib import Path

import pytest

from app.processors import office_convert


def test_missing_soffice_raises_clear_error(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(office_convert, "find_soffice", lambda: None)
    source = tmp_path / "slides.ppt"
    source.write_bytes(b"ppt")
    with pytest.raises(RuntimeError, match="LibreOffice"):
        office_convert.convert_ppt_to_pptx(source, tmp_path / "out")


def test_convert_returns_pptx_and_uses_ascii_staging(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(office_convert, "find_soffice", lambda: "/fake/soffice")
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        out_dir = Path(cmd[cmd.index("--outdir") + 1])
        (out_dir / "source.pptx").write_bytes(b"pptx")

    monkeypatch.setattr(office_convert.subprocess, "run", fake_run)
    source = tmp_path / "Bài giảng (1).ppt"
    source.write_bytes(b"ppt")
    target = office_convert.convert_ppt_to_pptx(source, tmp_path / "out")
    assert target.name == "source.pptx"
    assert target.is_file()
    assert calls[0][-1].endswith("source.ppt")
    assert "--headless" in calls[0]


def test_convert_failure_is_reported(tmp_path: Path, monkeypatch):
    import subprocess

    monkeypatch.setattr(office_convert, "find_soffice", lambda: "/fake/soffice")

    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, stderr="boom")

    monkeypatch.setattr(office_convert.subprocess, "run", fake_run)
    source = tmp_path / "slides.ppt"
    source.write_bytes(b"ppt")
    with pytest.raises(RuntimeError, match="boom"):
        office_convert.convert_ppt_to_pptx(source, tmp_path / "out")


def test_convert_without_output_file_fails(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(office_convert, "find_soffice", lambda: "/fake/soffice")
    monkeypatch.setattr(office_convert.subprocess, "run", lambda cmd, **kwargs: None)
    source = tmp_path / "slides.ppt"
    source.write_bytes(b"ppt")
    with pytest.raises(RuntimeError, match="no .pptx"):
        office_convert.convert_ppt_to_pptx(source, tmp_path / "out")
