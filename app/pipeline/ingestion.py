from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.chunking.text_chunker import TextChunker
from app.config.settings import Settings
from app.ids import file_sha256, nfc, relative_posix
from app.index_manifest import IndexManifest
from app.loaders.base import detect_kind, iter_input_files
from app.loaders.docling_loader import DoclingLoader
from app.loaders.image_loader import ImageLoader
from app.loaders.text_loader import TextLoader
from app.loaders.video_loader import VideoLoader
from app.pipeline.indexing import IndexingService
from app.processors.video_checkpoint import VIDEO_PIPELINE_VERSION
from app.processors.video_metadata import probe_duration
from app.storage.local import LocalFilesystemStore
from app.vectorstore.chroma import ChromaVectorStore

logger = logging.getLogger(__name__)


@dataclass
class FileIngestResult:
    path: str
    status: str
    document_id: str | None = None
    error: str | None = None
    duration_s: float = 0.0


@dataclass
class IngestReport:
    indexed: list[FileIngestResult] = field(default_factory=list)
    skipped_unchanged: list[FileIngestResult] = field(default_factory=list)
    reindexed_changed: list[FileIngestResult] = field(default_factory=list)
    skipped_video: list[FileIngestResult] = field(default_factory=list)
    failed: list[FileIngestResult] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "indexed": len(self.indexed),
            "skipped_unchanged": len(self.skipped_unchanged),
            "reindexed_changed": len(self.reindexed_changed),
            "skipped_video": len(self.skipped_video),
            "failed": len(self.failed),
        }


class IngestionPipeline:
    def __init__(
        self,
        settings: Settings,
        vector_store: ChromaVectorStore,
        object_store: LocalFilesystemStore,
        manifest: IndexManifest,
        indexer: IndexingService,
        text_chunker: TextChunker,
        docling_loader: DoclingLoader | None = None,
        image_loader: ImageLoader | None = None,
        text_loader: TextLoader | None = None,
        video_loader: VideoLoader | None = None,
    ) -> None:
        self.settings = settings
        self.vector_store = vector_store
        self.object_store = object_store
        self.manifest = manifest
        self.indexer = indexer
        self.text_chunker = text_chunker
        self.docling_loader = docling_loader
        self.image_loader = image_loader
        self.text_loader = text_loader or TextLoader(settings.project_root)
        self.video_loader = video_loader
        self._seen_hashes: set[str] = set()
        self._rechunk = False
        self._no_video = False

    def ingest(
        self, path: str | Path, *, rechunk: bool = False, no_video: bool = False
    ) -> IngestReport:
        self._rechunk = rechunk
        self._no_video = no_video
        target = Path(path).expanduser()
        if not target.is_absolute():
            target = (self.settings.project_root / target).resolve()
        files = iter_input_files(target)
        if not files:
            logger.info("No supported files found at %s", target)
        report = IngestReport()
        self._seen_hashes = set()
        for file_path in files:
            if self._no_video and detect_kind(file_path) == "video":
                relative = relative_posix(file_path, self.settings.project_root)
                logger.info("skipped (video) %s", file_path.name)
                report.skipped_video.append(
                    FileIngestResult(path=relative, status="skipped_video")
                )
                continue
            result = self.ingest_file(file_path)
            getattr(report, result.status).append(result)
        counts = report.counts()
        logger.info(
            "Ingest complete indexed=%s skipped_unchanged=%s reindexed_changed=%s skipped_video=%s failed=%s",
            counts["indexed"],
            counts["skipped_unchanged"],
            counts["reindexed_changed"],
            counts["skipped_video"],
            counts["failed"],
        )
        for item in report.failed:
            logger.error("Failed %s: %s", item.path, item.error)
        self._maybe_rebuild_bm25(report)
        return report

    def _maybe_rebuild_bm25(self, report: IngestReport) -> None:
        if not self.settings.hybrid_search:
            return
        path = self.settings.resolve_path(self.settings.bm25_path)
        changed = bool(report.indexed or report.reindexed_changed)
        if not changed and path.exists():
            return
        try:
            from app.retrieval.sparse import persist_bm25

            persist_bm25(
                self.vector_store,
                self.settings.text_collection,
                path,
            )
        except Exception:
            logger.exception("BM25 rebuild after ingest failed")

    def ingest_file(self, path: Path) -> FileIngestResult:
        started = time.perf_counter()
        relative = relative_posix(path, self.settings.project_root)
        try:
            document_id = file_sha256(path)
            if document_id in self._seen_hashes:
                return FileIngestResult(
                    path=relative,
                    status="skipped_unchanged",
                    document_id=document_id,
                    duration_s=time.perf_counter() - started,
                )
            self._seen_hashes.add(document_id)

            kind = detect_kind(path)
            logger.info("File detected %s kind=%s", path.name, kind)
            if kind is None:
                raise ValueError(f"Unsupported file type: {path.suffix}")

            status = "indexed"
            previous = self.manifest.get_hash_for_path(relative)
            if previous and previous != document_id:
                logger.info("Content changed for %s; deleting old vectors", relative)
                self._delete_document(previous)
                status = "reindexed_changed"

            if kind == "video":
                target_duration = self._video_target_duration(path)
                if self.manifest.is_video_complete(document_id, target_duration) and self._has_vectors(
                    document_id
                ):
                    logger.info("skipped (unchanged) %s", path.name)
                    self._touch_manifest(document_id, relative, path)
                    return FileIngestResult(
                        path=relative,
                        status="skipped_unchanged",
                        document_id=document_id,
                        duration_s=time.perf_counter() - started,
                    )
                if self.manifest.is_indexed(document_id) or self._has_vectors(document_id):
                    logger.info(
                        "Video %s incomplete or old pipeline; reindexing without dropping audio/transcript checkpoints",
                        path.name,
                    )
                    self._delete_vectors(document_id)
                    status = "reindexed_changed"
            elif self._already_indexed(document_id):
                if self._should_rechunk(document_id, kind):
                    logger.info("Rechunking %s profile=%s", path.name, self.settings.chunk_profile())
                    self._delete_vectors(document_id)
                    status = "reindexed_changed"
                else:
                    logger.info("skipped (unchanged) %s", path.name)
                    self._touch_manifest(document_id, relative, path)
                    return FileIngestResult(
                        path=relative,
                        status="skipped_unchanged",
                        document_id=document_id,
                        duration_s=time.perf_counter() - started,
                    )

            content_types = self._process(path, document_id, kind)
            extra = None
            if kind == "video" and self.video_loader is not None:
                extra = {
                    "processed_duration": self.video_loader.last_stats.get("processed_duration"),
                    "video_pipeline_version": self.video_loader.last_stats.get(
                        "video_pipeline_version", VIDEO_PIPELINE_VERSION
                    ),
                    "candidate_frames": self.video_loader.last_stats.get("candidate_frames"),
                    "selected_frames": self.video_loader.last_stats.get("selected_frames"),
                }
            elif kind != "video":
                extra = {"chunk_profile": self.settings.chunk_profile()}
            self.manifest.record(
                document_id,
                relative_path=relative,
                filename=nfc(path.name),
                file_type=path.suffix.lower().lstrip("."),
                content_types=content_types,
                extra=extra,
            )
            duration = time.perf_counter() - started
            logger.info("Indexed %s in %.2fs types=%s", path.name, duration, content_types)
            return FileIngestResult(
                path=relative,
                status=status,
                document_id=document_id,
                duration_s=duration,
            )
        except Exception as exc:
            logger.exception("Ingest failed for %s", path)
            return FileIngestResult(
                path=relative,
                status="failed",
                error=str(exc),
                duration_s=time.perf_counter() - started,
            )

    def _touch_manifest(self, document_id: str, relative: str, path: Path) -> None:
        entry = self.manifest.get_by_hash(document_id) or {}
        extra = {
            key: value
            for key, value in entry.items()
            if key not in {"relative_path", "filename", "file_type", "content_types"}
        }
        self.manifest.record(
            document_id,
            relative_path=relative,
            filename=nfc(path.name),
            file_type=path.suffix.lower().lstrip("."),
            content_types=entry.get("content_types") or [],
            extra=extra or None,
        )

    def _should_rechunk(self, document_id: str, kind: str) -> bool:
        if kind == "video":
            return False
        if self._rechunk:
            return True
        entry = self.manifest.get_by_hash(document_id) or {}
        stored = entry.get("chunk_profile")
        if not stored:
            return False
        return stored != self.settings.chunk_profile()

    def _already_indexed(self, document_id: str) -> bool:
        in_manifest = self.manifest.is_indexed(document_id)
        return in_manifest and self._has_vectors(document_id)

    def _has_vectors(self, document_id: str) -> bool:
        in_text = self.vector_store.has_document(self.settings.text_collection, document_id)
        in_visual = self.vector_store.has_document(self.settings.visual_collection, document_id)
        return in_text or in_visual

    def _video_target_duration(self, path: Path) -> float:
        probed = probe_duration(path)
        cap = self.settings.video_max_duration
        if cap is not None and cap > 0:
            return min(probed, cap)
        return probed

    def _delete_vectors(self, document_id: str) -> None:
        self.vector_store.delete(self.settings.text_collection, where={"document_id": document_id})
        self.vector_store.delete(self.settings.visual_collection, where={"document_id": document_id})

    def _delete_document(self, document_id: str) -> None:
        self._delete_vectors(document_id)
        self.object_store.delete_prefix(f"images/{document_id}")
        self.object_store.delete_prefix(f"frames/{document_id}")
        self.object_store.delete_prefix(f"audio/{document_id}.wav")
        self.object_store.delete_prefix(f"videos/{document_id}")
        self.object_store.delete_prefix(f"tmp/{document_id}")
        self.manifest.remove_hash(document_id)

    def _process(self, path: Path, document_id: str, kind: str) -> list[str]:
        if kind == "document":
            if self.docling_loader is None:
                raise RuntimeError("Docling loader is not available")
            loaded = self.docling_loader.load(path, document_id)
            chunks = self.text_chunker.chunk_blocks(
                document_id, loaded.text_blocks, file_type=loaded.asset.file_type
            )
            logger.info("Chunks generated: %s", len(chunks))
            return self.indexer.index_document(loaded, chunks)
        if kind == "text":
            loaded = self.text_loader.load(path, document_id)
            chunks = self.text_chunker.chunk_blocks(
                document_id, loaded.text_blocks, file_type=loaded.asset.file_type
            )
            return self.indexer.index_document(loaded, chunks)
        if kind == "image":
            if self.image_loader is None:
                raise RuntimeError("Image loader is not available")
            loaded = self.image_loader.load(path, document_id)
            chunks = self.text_chunker.chunk_blocks(
                document_id, loaded.text_blocks, file_type=loaded.asset.file_type
            )
            return self.indexer.index_document(loaded, chunks)
        if kind == "video":
            if self.video_loader is None:
                raise RuntimeError("Video loader is not available")
            loaded = self.video_loader.load(path, document_id)
            return self.indexer.index_video(loaded)
        raise ValueError(f"Unknown kind {kind}")
