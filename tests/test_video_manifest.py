from app.index_manifest import IndexManifest
from app.processors.video_checkpoint import VIDEO_PIPELINE_VERSION
from app.processors.video_frames import expected_coarse_count


def test_capped_video_is_not_complete(tmp_path):
    manifest = IndexManifest(tmp_path / "manifest.json")
    manifest.record(
        "abc",
        relative_path="assets/test/buoi_3.mp4",
        filename="buoi_3.mp4",
        file_type="mp4",
        content_types=["text"],
        extra={"processed_duration": 60, "video_pipeline_version": VIDEO_PIPELINE_VERSION},
    )
    assert manifest.is_video_complete("abc", 60)
    assert not manifest.is_video_complete("abc", 14400)


def test_old_manifest_without_duration_is_incomplete(tmp_path):
    manifest = IndexManifest(tmp_path / "manifest.json")
    manifest.record(
        "abc",
        relative_path="assets/test/buoi_3.mp4",
        filename="buoi_3.mp4",
        file_type="mp4",
        content_types=["text"],
    )
    assert not manifest.is_video_complete("abc", 60)


def test_old_pipeline_version_must_reindex(tmp_path):
    manifest = IndexManifest(tmp_path / "manifest.json")
    manifest.record(
        "abc",
        relative_path="a.mp4",
        filename="a.mp4",
        file_type="mp4",
        content_types=["text"],
        extra={"processed_duration": 14400, "video_pipeline_version": "v1-uniform"},
    )
    assert not manifest.is_video_complete("abc", 14400)


def test_coarse_count_four_hour_math():
    assert expected_coarse_count(14400, 10) == 1440
    assert expected_coarse_count(60, 10) == 6
    assert expected_coarse_count(0, 10) == 0
