from __future__ import annotations

import logging
from pathlib import Path

from app.ids import nfc, relative_posix, vector_id
from app.loaders.base import LoadedDocument
from app.models.document import DocumentAsset
from app.models.image import ImageAsset
from app.processors.image import load_rgb
from app.processors.ocr import OCREngine, NullOCR
from app.storage.local import LocalFilesystemStore

logger = logging.getLogger(__name__)


class ImageLoader:
    def __init__(
        self,
        project_root: Path,
        object_store: LocalFilesystemStore,
        ocr: OCREngine | None = None,
    ) -> None:
        self.project_root = project_root
        self.object_store = object_store
        self.ocr = ocr or NullOCR()

    def load(self, path: Path, document_id: str) -> LoadedDocument:
        relative = relative_posix(path, self.project_root)
        asset = DocumentAsset(
            id=document_id,
            source=str(path.resolve()),
            file_name=nfc(path.name),
            relative_path=relative,
            file_type=path.suffix.lower().lstrip("."),
        )
        image = load_rgb(path)
        stored = self.object_store.put_image(f"images/{document_id}/original.png", image)
        ocr_text = ""
        try:
            ocr_text = self.ocr.extract_text(image)
        except Exception:
            logger.exception("OCR failed for %s", path.name)
        image_asset = ImageAsset(
            id=vector_id(document_id, "image", 0),
            document_id=document_id,
            path=stored,
            caption=None,
            ocr_text=ocr_text or None,
            metadata={"image_path": stored},
        )
        blocks = []
        if ocr_text:
            blocks.append({"text": ocr_text, "page_number": None, "section": None})
        logger.info("Image loader stored %s (ocr_chars=%s)", path.name, len(ocr_text))
        return LoadedDocument(asset=asset, text_blocks=blocks, images=[image_asset])
