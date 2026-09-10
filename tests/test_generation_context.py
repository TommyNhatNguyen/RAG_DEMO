from app.generation.context import collect_source_paths, format_hits, generation_k, relative_path_for_hit
from app.models.retrieval import RetrievalResult


def _hit(
    *,
    content: str | None,
    content_type: str = "text",
    relative_path: str | None = "assets/test/bai_tap_chuong_3.docx",
    page_number: int | None = None,
    start_time: float | None = None,
    end_time: float | None = None,
    chunk_index: int | None = 0,
    filename: str | None = None,
    extra: dict | None = None,
) -> RetrievalResult:
    meta: dict = {}
    if relative_path is not None:
        meta["relative_path"] = relative_path
    if filename is not None:
        meta["filename"] = filename
    if page_number is not None:
        meta["page_number"] = page_number
    if start_time is not None:
        meta["start_time"] = start_time
    if end_time is not None:
        meta["end_time"] = end_time
    if chunk_index is not None:
        meta["chunk_index"] = chunk_index
    if extra:
        meta.update(extra)
    return RetrievalResult(
        id="h",
        score=0.9,
        content_type=content_type,
        content=content,
        metadata=meta,
    )


def test_format_hits_includes_path_page_and_type():
    text = format_hits(
        [
            _hit(
                content="Quan hệ phản xạ",
                content_type="text",
                relative_path="assets/test/bai_tap_chuong_3.docx",
                page_number=2,
                chunk_index=1,
            )
        ]
    )
    assert "assets/test/bai_tap_chuong_3.docx" in text
    assert "p.2" in text
    assert "text" in text
    assert "Quan hệ phản xạ" in text
    assert "#1" not in text


def test_format_hits_video_timestamps():
    text = format_hits(
        [
            _hit(
                content="transcript",
                content_type="video_segment",
                relative_path="assets/test/buoi_3.mp4",
                start_time=15.0,
                end_time=30.5,
                chunk_index=3,
            )
        ]
    )
    assert "video_segment" in text
    assert "@15-30.5s" in text
    assert "assets/test/buoi_3.mp4" in text


def test_format_hits_video_frame_timestamp():
    text = format_hits(
        [
            _hit(
                content="diagram",
                content_type="video_frame",
                relative_path="assets/test/buoi_3.mp4",
                start_time=15.0,
                end_time=30.0,
                extra={"timestamp": 22.0},
            )
        ]
    )
    assert "video_frame" in text
    assert "t=22s" in text
    assert "@15-30s" in text


def test_format_hits_truncates_at_max_chars():
    hits = [
        _hit(content="AAAA", relative_path="a.docx", chunk_index=0),
        _hit(content="BBBB", relative_path="b.docx", chunk_index=1),
    ]
    text = format_hits(hits, max_chars=40)
    assert "AAAA" in text
    assert "BBBB" not in text


def test_format_hits_empty():
    assert format_hits([]) == "(Không có ngữ cảnh)"


def test_format_hits_empty_visual_stub():
    text = format_hits(
        [
            _hit(
                content="",
                content_type="image",
                relative_path="assets/slides/foo.pptx",
                page_number=2,
            )
        ]
    )
    assert "image" in text
    assert "assets/slides/foo.pptx" in text
    assert "Không có OCR/caption" in text


def test_format_hits_empty_video_segment_is_text_stub():
    text = format_hits(
        [
            _hit(
                content="",
                content_type="video_segment",
                relative_path="assets/test/buoi_3.mp4",
            )
        ]
    )
    assert "video_segment" in text
    assert "Không có nội dung" in text
    assert "Không có OCR/caption" not in text


def test_collect_source_paths_unique_and_relative():
    hits = [
        _hit(content="a", relative_path="assets/test/bai_tap_chuong_3.docx"),
        _hit(content="b", relative_path="assets/test/bai_tap_chuong_3.docx"),
        _hit(content="c", relative_path="assets/test/Chuong_3_quan_he.pptx"),
    ]
    paths = collect_source_paths(hits)
    assert paths.count("bai_tap_chuong_3.docx") == 1
    assert "Chuong_3_quan_he.pptx" in paths
    assert paths.startswith("- ")


def test_collect_source_paths_strips_absolute():
    hits = [
        _hit(
            content="a",
            relative_path=None,
            filename="/Users/me/project/assets/test/file.docx",
        )
    ]
    paths = collect_source_paths(hits)
    assert paths == "- file.docx"
    assert "/" not in paths.split("- ", 1)[-1]


def test_collect_source_paths_empty():
    assert collect_source_paths([]) == "- (không có)"


def test_relative_path_prefers_metadata(settings):
    hit = _hit(content="x", relative_path="assets/a.docx", filename="ignored.docx")
    assert relative_path_for_hit(hit) == "assets/a.docx"
    assert generation_k(settings, None) == max(settings.retriever_k, settings.generation_k)
    assert generation_k(settings, 3) == 3
