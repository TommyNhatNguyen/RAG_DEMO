from __future__ import annotations

import logging
import re
from pathlib import Path

from app.ids import nfc, relative_posix
from app.loaders.base import LoadedDocument
from app.models.document import DocumentAsset
from app.models.image import ImageAsset

logger = logging.getLogger(__name__)

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


class TextLoader:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def load(self, path: Path, document_id: str) -> LoadedDocument:
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = relative_posix(path, self.project_root)
        asset = DocumentAsset(
            id=document_id,
            source=str(path.resolve()),
            file_name=nfc(path.name),
            relative_path=relative,
            file_type=path.suffix.lower().lstrip("."),
        )
        blocks: list[dict] = []
        if path.suffix.lower() in {".md", ".markdown"}:
            section = None
            buf: list[str] = []
            for line in text.splitlines():
                match = HEADING_RE.match(line.strip())
                if match:
                    if buf:
                        blocks.append({"text": "\n".join(buf).strip(), "page_number": None, "section": section})
                        buf = []
                    section = match.group(2).strip()
                    continue
                buf.append(line)
            if buf:
                blocks.append({"text": "\n".join(buf).strip(), "page_number": None, "section": section})
        else:
            blocks.append({"text": text.strip(), "page_number": None, "section": None})
        blocks = [b for b in blocks if b["text"]]
        logger.info("Text loader parsed %s blocks from %s", len(blocks), asset.file_name)
        return LoadedDocument(asset=asset, text_blocks=blocks, images=[], tables=[], page_images=[])
