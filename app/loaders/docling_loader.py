from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.config.settings import Settings
from app.ids import nfc, relative_posix, vector_id
from app.loaders.base import LoadedDocument
from app.models.document import DocumentAsset, TableAsset
from app.models.image import ImageAsset
from app.processors.image import to_rgb
from app.processors.ocr import OCREngine, NullOCR
from app.storage.local import LocalFilesystemStore

logger = logging.getLogger(__name__)

MIN_NATIVE_TEXT = 40


class DoclingLoader:
    def __init__(
        self,
        settings: Settings,
        object_store: LocalFilesystemStore,
        ocr: OCREngine | None = None,
    ) -> None:
        self.settings = settings
        self.object_store = object_store
        self.ocr = ocr or NullOCR()
        self._converter = None

    def _get_converter(self):
        if self._converter is not None:
            return self._converter
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        pipeline = PdfPipelineOptions(
            do_ocr=False,
            do_table_structure=True,
            generate_picture_images=self.settings.generate_picture_images,
            generate_page_images=self.settings.generate_page_images,
            images_scale=1.0,
        )
        self._converter = DocumentConverter(
            allowed_formats=[
                InputFormat.PDF,
                InputFormat.DOCX,
                InputFormat.PPTX,
                InputFormat.IMAGE,
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline),
            },
        )
        return self._converter

    def load(self, path: Path, document_id: str) -> LoadedDocument:
        logger.info("Docling parsing %s", path.name)
        converter = self._get_converter()
        result = converter.convert(str(path))
        doc = result.document
        relative = relative_posix(path, self.settings.project_root)
        file_type = path.suffix.lower().lstrip(".")
        asset = DocumentAsset(
            id=document_id,
            source=str(path.resolve()),
            file_name=nfc(path.name),
            relative_path=relative,
            file_type=file_type,
        )

        text_blocks, native_by_page = self._extract_text(doc)
        tables = self._extract_tables(doc, document_id, asset)
        images = self._extract_pictures(doc, document_id, asset)
        page_images = self._extract_page_images(doc, document_id, asset, native_by_page)

        if not any(len(t) >= MIN_NATIVE_TEXT for t in native_by_page.values()) and page_images:
            logger.info("Little native text in %s; running OCR on page images", path.name)
            for img in page_images:
                try:
                    from PIL import Image

                    pil = Image.open(img.path)
                    ocr_text = self.ocr.extract_text(pil)
                except Exception:
                    logger.exception("OCR failed for page image %s", img.path)
                    ocr_text = ""
                img.ocr_text = ocr_text or None
                if ocr_text:
                    text_blocks.append(
                        {
                            "text": ocr_text,
                            "page_number": img.page_number,
                            "section": None,
                        }
                    )

        logger.info(
            "Docling extracted %s text blocks, %s tables, %s images from %s",
            len(text_blocks),
            len(tables),
            len(images) + len(page_images),
            path.name,
        )
        return LoadedDocument(
            asset=asset,
            text_blocks=text_blocks,
            tables=tables,
            images=images,
            page_images=page_images,
            native_text_by_page=native_by_page,
        )

    def _page_no(self, item: Any) -> int | None:
        prov = getattr(item, "prov", None) or []
        if not prov:
            return None
        page = getattr(prov[0], "page_no", None)
        return int(page) if page is not None else None

    def _extract_text(self, doc) -> tuple[list[dict], dict[int, str]]:
        from docling_core.types.doc import DocItemLabel

        heading_labels = {DocItemLabel.SECTION_HEADER, DocItemLabel.TITLE}
        skip_labels = {
            DocItemLabel.PAGE_FOOTER,
            DocItemLabel.PAGE_HEADER,
            DocItemLabel.FOOTNOTE,
            DocItemLabel.PICTURE,
            DocItemLabel.TABLE,
        }
        section: str | None = None
        blocks: list[dict] = []
        native_by_page: dict[int, list[str]] = {}

        for item, _level in doc.iterate_items():
            label = getattr(item, "label", None)
            text = (getattr(item, "text", None) or "").strip()
            if not text:
                continue
            page = self._page_no(item)
            if label in heading_labels:
                section = text
                blocks.append({"text": text, "page_number": page, "section": section})
                if page is not None:
                    native_by_page.setdefault(page, []).append(text)
                continue
            if label in skip_labels:
                continue
            blocks.append({"text": text, "page_number": page, "section": section})
            if page is not None:
                native_by_page.setdefault(page, []).append(text)

        joined = {page: "\n".join(parts) for page, parts in native_by_page.items()}
        blocks = [b for b in blocks if b["text"]]
        return blocks, joined

    def _extract_tables(self, doc, document_id: str, asset: DocumentAsset) -> list[TableAsset]:
        tables: list[TableAsset] = []
        for index, table in enumerate(doc.tables or []):
            markdown = ""
            try:
                markdown = table.export_to_markdown(doc)
            except TypeError:
                markdown = table.export_to_markdown()
            except Exception:
                logger.exception("Table markdown export failed")
            if not markdown:
                continue
            data = getattr(table, "data", None)
            tables.append(
                TableAsset(
                    id=vector_id(document_id, "table", index),
                    document_id=document_id,
                    page_number=self._page_no(table),
                    rows=getattr(data, "num_rows", None),
                    columns=getattr(data, "num_cols", None),
                    markdown=markdown,
                    metadata={
                        "filename": asset.file_name,
                        "relative_path": asset.relative_path,
                    },
                )
            )
        return tables

    def _extract_pictures(self, doc, document_id: str, asset: DocumentAsset) -> list[ImageAsset]:
        images: list[ImageAsset] = []
        for index, picture in enumerate(doc.pictures or []):
            pil = None
            try:
                if hasattr(picture, "get_image"):
                    pil = picture.get_image(doc)
                elif getattr(picture, "image", None) is not None:
                    image_ref = picture.image
                    pil = getattr(image_ref, "pil_image", None)
            except Exception:
                logger.exception("Picture extract failed")
            if pil is None:
                continue
            pil = to_rgb(pil)
            stored = self.object_store.put_image(
                f"images/{document_id}/picture_{index:03d}.png",
                pil,
            )
            caption = getattr(picture, "caption", None)
            if caption is not None and not isinstance(caption, str):
                caption = getattr(caption, "text", None) or str(caption)
            images.append(
                ImageAsset(
                    id=vector_id(document_id, "image", index),
                    document_id=document_id,
                    path=stored,
                    page_number=self._page_no(picture),
                    caption=caption,
                    metadata={
                        "image_path": stored,
                        "filename": asset.file_name,
                        "relative_path": asset.relative_path,
                    },
                )
            )
        return images

    def _extract_page_images(
        self,
        doc,
        document_id: str,
        asset: DocumentAsset,
        native_by_page: dict[int, str],
    ) -> list[ImageAsset]:
        images: list[ImageAsset] = []
        pages = getattr(doc, "pages", None) or {}
        is_pptx = asset.file_type == "pptx"
        for page_no, page in pages.items():
            page_int = int(page_no)
            native = native_by_page.get(page_int, "")
            # Keep a page image for every PDF/PPTX page so the VL retriever and
            # Qwen-VL answerer can use layout, formulas, diagrams, and text
            # that native extraction may flatten or omit. DOCX keeps the
            # lightweight fallback for image-heavy pages and embedded pictures.
            need_page = (
                asset.file_type in {"pdf", "pptx"}
                or len(native.strip()) < MIN_NATIVE_TEXT
            )
            if not need_page:
                continue
            pil = None
            image_ref = getattr(page, "image", None)
            if image_ref is not None:
                pil = getattr(image_ref, "pil_image", image_ref)
                if hasattr(pil, "save") is False and hasattr(image_ref, "pil_image"):
                    pil = image_ref.pil_image
            if pil is None:
                continue
            try:
                pil = to_rgb(pil)
            except Exception:
                continue
            stored = self.object_store.put_image(
                f"images/{document_id}/page_{page_int:03d}.png",
                pil,
            )
            images.append(
                ImageAsset(
                    id=vector_id(document_id, "page", page_int),
                    document_id=document_id,
                    path=stored,
                    page_number=page_int,
                    metadata={
                        "image_path": stored,
                        "filename": asset.file_name,
                        "relative_path": asset.relative_path,
                        "slide_number": page_int if is_pptx else None,
                    },
                )
            )
        return images
