from app.loaders.base import LoadedVideo
from app.models.video import VideoAsset, VideoSegment
from app.pipeline.indexing import IndexingService
from app.vectorstore.chroma import ChromaVectorStore
from tests.conftest import FakeTextEmbedder, FakeVLEmbedder


def test_index_video_one_vector_per_selected_frame(settings):
    store = ChromaVectorStore(
        settings.resolve_path(settings.chroma_path),
        settings.text_collection,
        settings.visual_collection,
    )
    text = FakeTextEmbedder()
    visual = FakeVLEmbedder()
    indexer = IndexingService(settings, store, text, visual)
    asset = VideoAsset(
        id="vidhash",
        source="/tmp/lecture.mp4",
        file_name="lecture.mp4",
        relative_path="assets/test/lecture.mp4",
        duration=60,
        metadata={},
    )
    segment = VideoSegment(
        id="vidhash:video_segment:0",
        video_id="vidhash",
        start_time=0,
        end_time=30,
        transcript="B-tree indexing",
        frame_paths=["/tmp/t5000.jpg", "/tmp/t20000.jpg"],
        frame_timestamps=[5.0, 20.0],
        ocr_texts=["Slide A", "Slide B"],
    )
    types = indexer.index_video(LoadedVideo(asset=asset, segments=[segment], full_transcript="B-tree indexing"))
    assert "text" in types
    assert "video_frame" in types
    vis = store.get(settings.visual_collection)
    assert len(vis["ids"]) == 2
    assert all("video_frame" in item for item in vis["ids"])
    metas = vis["metadatas"]
    assert {m.get("timestamp") for m in metas} == {5.0, 20.0}
    assert all(m.get("content_type") == "video_frame" for m in metas)
    assert visual.image_calls
    assert len(visual.image_calls[0]) == 2
