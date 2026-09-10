from app.ids import file_sha256
from app.chunking.text_chunker import TextChunker
from app.config.settings import Settings
from app.index_manifest import IndexManifest
from app.loaders.base import LoadedVideo
from app.models.video import VideoAsset, VideoSegment
from app.pipeline.indexing import IndexingService
from app.pipeline.ingestion import IngestionPipeline
from app.processors.video_checkpoint import VIDEO_PIPELINE_VERSION
from app.storage.local import LocalFilesystemStore
from app.vectorstore.chroma import ChromaVectorStore
from tests.conftest import FakeTextEmbedder, FakeVLEmbedder


def _pipeline(settings: Settings, text_embedder: FakeTextEmbedder):
    store = ChromaVectorStore(
        settings.resolve_path(settings.chroma_path),
        settings.text_collection,
        settings.visual_collection,
    )
    object_store = LocalFilesystemStore(settings.resolve_path(settings.storage_root))
    manifest = IndexManifest(settings.resolve_path(settings.manifest_path))
    indexer = IndexingService(settings, store, text_embedder, FakeVLEmbedder())
    return IngestionPipeline(
        settings=settings,
        vector_store=store,
        object_store=object_store,
        manifest=manifest,
        indexer=indexer,
        text_chunker=TextChunker(settings.chunk_size, settings.chunk_overlap),
    ), store, text_embedder


def test_ingest_twice_skips_and_does_not_reembed(settings):
    embedder = FakeTextEmbedder()
    pipeline, store, embedder = _pipeline(settings, embedder)
    path = settings.project_root / "notes.txt"
    path.write_text("Quan he phan xa tren tap {1,2,3,4}. " * 8)

    first = pipeline.ingest(path)
    assert first.counts()["indexed"] == 1
    count = store.count(settings.text_collection)
    calls = len(embedder.document_calls)

    second = pipeline.ingest(path)
    assert second.counts()["skipped_unchanged"] == 1
    assert store.count(settings.text_collection) == count
    assert len(embedder.document_calls) == calls


def test_copy_to_new_path_does_not_duplicate(settings):
    embedder = FakeTextEmbedder()
    pipeline, store, _embedder = _pipeline(settings, embedder)
    src = settings.project_root / "a.txt"
    src.write_text("same bytes here for hashing")
    pipeline.ingest(src)
    count = store.count(settings.text_collection)

    copy = settings.project_root / "Chương 1.txt"
    copy.write_bytes(src.read_bytes())
    result = pipeline.ingest(copy)
    assert result.counts()["skipped_unchanged"] == 1
    assert store.count(settings.text_collection) == count


def test_content_change_replaces_vectors(settings):
    embedder = FakeTextEmbedder()
    pipeline, store, _embedder = _pipeline(settings, embedder)
    path = settings.project_root / "doc.txt"
    path.write_text("version one of the document content")
    pipeline.ingest(path)
    old_ids = store.get(settings.text_collection)["ids"]
    path.write_text("version two of the document content is different")
    result = pipeline.ingest(path)
    assert result.counts()["reindexed_changed"] == 1
    new_ids = store.get(settings.text_collection)["ids"]
    assert old_ids
    assert new_ids
    assert set(old_ids).isdisjoint(set(new_ids))
    assert len(new_ids) == store.count(settings.text_collection)


def test_mixed_directory_skips_indexed(settings):
    embedder = FakeTextEmbedder()
    pipeline, store, _embedder = _pipeline(settings, embedder)
    one = settings.project_root / "one.txt"
    two = settings.project_root / "two.txt"
    one.write_text("first file contents for ingest")
    two.write_text("second file contents for ingest")
    pipeline.ingest(one)
    report = pipeline.ingest(settings.project_root)
    assert report.counts()["skipped_unchanged"] == 1
    assert report.counts()["indexed"] == 1


class _FakeVideoLoader:
    def __init__(self) -> None:
        self.calls = 0
        self.last_stats = {
            "processed_duration": 14400.0,
            "video_pipeline_version": VIDEO_PIPELINE_VERSION,
            "candidate_frames": 10,
            "selected_frames": 3,
        }

    def load(self, path, document_id):
        self.calls += 1
        asset = VideoAsset(
            id=document_id,
            source=str(path),
            file_name=path.name,
            relative_path=path.name,
            duration=14400,
            metadata=dict(self.last_stats),
        )
        segment = VideoSegment(
            id=f"{document_id}:video_segment:0",
            video_id=document_id,
            start_time=0,
            end_time=30,
            transcript="full lecture transcript",
            frame_paths=[],
        )
        return LoadedVideo(asset=asset, segments=[segment], full_transcript="full lecture transcript")


def test_capped_video_manifest_does_not_skip_full_ingest(settings, monkeypatch):
    monkeypatch.setattr("app.pipeline.ingestion.probe_duration", lambda _path: 14400.0)
    embedder = FakeTextEmbedder()
    pipeline, _store, _ = _pipeline(settings, embedder)
    loader = _FakeVideoLoader()
    pipeline.video_loader = loader
    path = settings.project_root / "buoi_3.mp4"
    path.write_bytes(b"fake-mp4-bytes")
    document_id = file_sha256(path)
    pipeline.manifest.record(
        document_id,
        relative_path="buoi_3.mp4",
        filename="buoi_3.mp4",
        file_type="mp4",
        content_types=["text"],
        extra={"processed_duration": 60, "video_pipeline_version": VIDEO_PIPELINE_VERSION},
    )
    report = pipeline.ingest(path)
    assert report.counts()["skipped_unchanged"] == 0
    assert loader.calls == 1
    assert report.counts()["reindexed_changed"] + report.counts()["indexed"] == 1
    entry = pipeline.manifest.get_by_hash(document_id)
    assert entry["processed_duration"] == 14400.0


def test_rechunk_reindexes_text_and_skips_video(settings):
    embedder = FakeTextEmbedder()
    pipeline, store, embedder = _pipeline(settings, embedder)
    path = settings.project_root / "notes.txt"
    path.write_text("Quan he phan xa tren tap {1,2,3,4}. " * 8)
    first = pipeline.ingest(path)
    assert first.counts()["indexed"] == 1
    document_id = first.indexed[0].document_id
    entry = pipeline.manifest.get_by_hash(document_id)
    assert entry["chunk_profile"] == settings.chunk_profile()
    calls = len(embedder.document_calls)
    skipped = pipeline.ingest(path)
    assert skipped.counts()["skipped_unchanged"] == 1
    again = pipeline.ingest(path, rechunk=True)
    assert again.counts()["reindexed_changed"] == 1
    assert len(embedder.document_calls) > calls
    assert store.count(settings.text_collection) >= 1

    pipeline._rechunk = True
    assert pipeline._should_rechunk("unused", "video") is False
    assert pipeline._should_rechunk(document_id, "text") is True


def test_chunk_profile_change_reindexes_without_flag(settings):
    embedder = FakeTextEmbedder()
    pipeline, _store, embedder = _pipeline(settings, embedder)
    path = settings.project_root / "notes.txt"
    path.write_text("Quan he phan xa tren tap {1,2,3,4}. " * 8)
    pipeline.ingest(path)
    calls = len(embedder.document_calls)
    settings.chunk_size_txt = 200
    settings.chunk_overlap_txt = 20
    changed = pipeline.ingest(path)
    assert changed.counts()["reindexed_changed"] == 1
    assert len(embedder.document_calls) > calls


def test_missing_chunk_profile_does_not_auto_rechunk(settings):
    embedder = FakeTextEmbedder()
    pipeline, _store, embedder = _pipeline(settings, embedder)
    path = settings.project_root / "legacy.txt"
    path.write_text("legacy indexed without chunk_profile field")
    first = pipeline.ingest(path)
    document_id = first.indexed[0].document_id
    entry = pipeline.manifest.get_by_hash(document_id)
    pipeline.manifest.record(
        document_id,
        relative_path=entry["relative_path"],
        filename=entry["filename"],
        file_type=entry["file_type"],
        content_types=entry.get("content_types") or [],
        extra={
            key: value
            for key, value in entry.items()
            if key
            not in {
                "relative_path",
                "filename",
                "file_type",
                "content_types",
                "chunk_profile",
            }
        }
        or None,
    )
    calls = len(embedder.document_calls)
    skipped = pipeline.ingest(path)
    assert skipped.counts()["skipped_unchanged"] == 1
    assert len(embedder.document_calls) == calls
