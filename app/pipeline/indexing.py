from __future__ import annotations

import logging
from typing import Any

from app.config.settings import Settings
from app.embeddings.base import TextEmbedder, VLEmbedder
from app.ids import vector_id
from app.loaders.base import LoadedDocument, LoadedVideo
from app.models.chunk import TextChunk
from app.models.document import DocumentAsset, TableAsset
from app.models.image import ImageAsset
from app.models.video import VideoSegment
from app.processors.video_checkpoint import VideoCheckpoint
from app.vectorstore.chroma import ChromaVectorStore

logger = logging.getLogger(__name__)


def course_from_relative_path(relative_path: str) -> str | None:
    parts = (relative_path or "").replace("\\", "/").lstrip("./").split("/")
    parts = [part for part in parts if part]
    if len(parts) >= 2 and parts[0] == "assets":
        return parts[1]
    return None


def base_metadata(
    asset: DocumentAsset,
    *,
    content_type: str,
    chunk_index: int,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "document_id": asset.id,
        "source": asset.source,
        "file_name": asset.file_name,
        "filename": asset.file_name,
        "relative_path": asset.relative_path,
        "file_type": asset.file_type,
        "content_type": content_type,
        "chunk_index": chunk_index,
    }
    course = course_from_relative_path(asset.relative_path)
    if course:
        meta["course"] = course
    if extra:
        meta.update(extra)
    return {key: value for key, value in meta.items() if value is not None}


class IndexingService:
    def __init__(
        self,
        settings: Settings,
        vector_store: ChromaVectorStore,
        text_embedder: TextEmbedder,
        vl_embedder: VLEmbedder | None = None,
    ) -> None:
        self.settings = settings
        self.vector_store = vector_store
        self.text_embedder = text_embedder
        self.vl_embedder = vl_embedder

    def index_document(
        self,
        loaded: LoadedDocument,
        text_chunks: list[TextChunk],
    ) -> list[str]:
        content_types: list[str] = []
        asset = loaded.asset
        text_ids: list[str] = []
        text_docs: list[str] = []
        text_meta: list[dict[str, Any]] = []

        for chunk in text_chunks:
            text_ids.append(chunk.id)
            text_docs.append(chunk.text)
            text_meta.append(
                base_metadata(
                    asset,
                    content_type="text",
                    chunk_index=chunk.chunk_index,
                    extra={"page_number": chunk.page_number, "section": chunk.section},
                )
            )
        for table in loaded.tables:
            text_ids.append(table.id)
            text_docs.append(table.markdown)
            text_meta.append(
                base_metadata(
                    asset,
                    content_type="table",
                    chunk_index=int(str(table.id).rsplit(":", 1)[-1] or 0),
                    extra={"page_number": table.page_number, "section": table.section},
                )
            )
        ocr_index = 0
        for image in loaded.images + loaded.page_images:
            if image.ocr_text:
                vid = vector_id(asset.id, "text", 10_000 + ocr_index)
                text_ids.append(vid)
                text_docs.append(image.ocr_text)
                text_meta.append(
                    base_metadata(
                        asset,
                        content_type="text",
                        chunk_index=10_000 + ocr_index,
                        extra={
                            "page_number": image.page_number,
                            "image_path": image.path,
                        },
                    )
                )
                ocr_index += 1

        if text_ids:
            vectors = self.text_embedder.embed_documents(text_docs, self.settings.text_batch_size)
            added, skipped = self.vector_store.add(
                self.settings.text_collection,
                text_ids,
                vectors,
                text_docs,
                text_meta,
            )
            logger.info("Indexed text vectors added=%s skipped=%s", added, skipped)
            content_types.append("text")

        visual_items = loaded.images + loaded.page_images
        if visual_items and self.vl_embedder is not None:
            try:
                self._index_images(asset, visual_items)
                content_types.append("image")
            except Exception:
                logger.exception("Visual indexing failed; text vectors were still stored")
        if loaded.tables:
            content_types.append("table")
        return sorted(set(content_types))

    def _index_images(self, asset: DocumentAsset, images: list[ImageAsset]) -> None:
        assert self.vl_embedder is not None
        ids: list[str] = []
        docs: list[str | None] = []
        metas: list[dict[str, Any]] = []
        inputs: list[str | dict] = []
        for image in images:
            content_type = "page" if ":page:" in image.id else "image"
            payload: str | dict
            if image.caption or image.ocr_text:
                payload = {"text": (image.caption or image.ocr_text or ""), "image": image.path}
            else:
                payload = image.path
            ids.append(image.id)
            docs.append(image.caption or image.ocr_text)
            metas.append(
                base_metadata(
                    asset,
                    content_type=content_type,
                    chunk_index=int(str(image.id).rsplit(":", 1)[-1] or 0),
                    extra={
                        "page_number": image.page_number,
                        "image_path": image.path,
                        "caption": image.caption,
                    },
                )
            )
            inputs.append(payload)
        vectors = self.vl_embedder.embed_images(inputs, self.settings.vl_batch_size)
        added, skipped = self.vector_store.add(
            self.settings.visual_collection,
            ids,
            vectors,
            docs,
            metas,
        )
        logger.info("Indexed visual vectors added=%s skipped=%s", added, skipped)

    def index_video(self, loaded: LoadedVideo) -> list[str]:
        asset = DocumentAsset(
            id=loaded.asset.id,
            source=loaded.asset.source,
            file_name=loaded.asset.file_name,
            relative_path=loaded.asset.relative_path,
            file_type="mp4",
        )
        content_types: list[str] = []
        text_ids: list[str] = []
        text_docs: list[str] = []
        text_meta: list[dict[str, Any]] = []
        for index, segment in enumerate(loaded.segments):
            if not segment.transcript:
                continue
            text_ids.append(vector_id(asset.id, "text", index))
            text_docs.append(segment.transcript)
            text_meta.append(
                base_metadata(
                    asset,
                    content_type="video_segment",
                    chunk_index=index,
                    extra={
                        "video_id": segment.video_id,
                        "start_time": segment.start_time,
                        "end_time": segment.end_time,
                    },
                )
            )
        if text_ids:
            logger.info("[6/7] Embedding transcript windows (%s)", len(text_ids))
            vectors = self.text_embedder.embed_documents(text_docs, self.settings.text_batch_size)
            self.vector_store.add(self.settings.text_collection, text_ids, vectors, text_docs, text_meta)
            content_types.append("text")

        if self.vl_embedder is not None:
            try:
                self._index_video_visual(asset, loaded.segments)
                content_types.append("video_frame")
            except Exception:
                logger.exception("Video visual indexing failed; transcript vectors were still stored")
        self._mark_video_indexed(loaded)
        return sorted(set(content_types))

    def _mark_video_indexed(self, loaded: LoadedVideo) -> None:
        import shutil
        from pathlib import Path

        meta = loaded.asset.metadata or {}
        checkpoint_path = meta.get("checkpoint_path")
        if checkpoint_path:
            VideoCheckpoint(Path(checkpoint_path)).update(stage="indexed")
        tmp = self.settings.resolve_path(self.settings.storage_root) / "tmp" / loaded.asset.id
        shutil.rmtree(tmp, ignore_errors=True)

    def _index_video_visual(self, asset: DocumentAsset, segments: list[VideoSegment]) -> None:
        assert self.vl_embedder is not None
        ids: list[str] = []
        docs: list[str | None] = []
        metas: list[dict[str, Any]] = []
        inputs: list[str | dict] = []
        used: set[int] = set()
        for segment in segments:
            for index, frame in enumerate(segment.frame_paths):
                timestamp = (
                    segment.frame_timestamps[index]
                    if index < len(segment.frame_timestamps)
                    else segment.start_time
                )
                ocr = segment.ocr_texts[index] if index < len(segment.ocr_texts) else ""
                chunk_index = int(round(float(timestamp) * 1000))
                while chunk_index in used:
                    chunk_index += 1
                used.add(chunk_index)
                text = (ocr or segment.transcript or "").strip() or None
                if text:
                    payload: str | dict = {"text": text, "image": frame}
                else:
                    payload = frame
                ids.append(vector_id(asset.id, "video_frame", chunk_index))
                docs.append(text)
                metas.append(
                    base_metadata(
                        asset,
                        content_type="video_frame",
                        chunk_index=chunk_index,
                        extra={
                            "video_id": segment.video_id,
                            "segment_id": segment.id,
                            "start_time": segment.start_time,
                            "end_time": segment.end_time,
                            "timestamp": timestamp,
                            "image_path": frame,
                        },
                    )
                )
                inputs.append(payload)
        if not ids:
            return
        logger.info("[7/7] Embedding video frames (%s)", len(ids))
        vectors = self.vl_embedder.embed_images(inputs, self.settings.vl_batch_size)
        added, skipped = self.vector_store.add(
            self.settings.visual_collection, ids, vectors, docs, metas
        )
        logger.info("Indexed video frame vectors added=%s skipped=%s", added, skipped)
