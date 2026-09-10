from pathlib import Path

from app.loaders.text_loader import TextLoader
from app.ids import file_sha256


def test_markdown_headings_become_sections(tmp_path: Path):
    path = tmp_path / "notes.md"
    path.write_text("# Intro\nHello\n\n## Details\nMore text\n")
    loaded = TextLoader(tmp_path).load(path, file_sha256(path))
    sections = [b["section"] for b in loaded.text_blocks]
    assert "Intro" in sections
    assert "Details" in sections
