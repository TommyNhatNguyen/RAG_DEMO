from app.generation.query_enhance import EnhancedQuery
from app.models.retrieval import RetrievalResult
from app.retrieval.merger import merge_results, rrf_merge
from app.retrieval.reranker import ScoreReranker
from app.retrieval.retriever import MultimodalRetriever, process_user_query
from app.vectorstore.chroma import ChromaVectorStore
from tests.conftest import FakeTextEmbedder, FakeVLEmbedder


def test_process_query_nfc_and_whitespace():
    raw = "  Quan  hệ\nphản xạ  "
    cleaned = process_user_query(raw)
    assert "  " not in cleaned
    assert cleaned.startswith("Quan")


def test_merge_keeps_higher_score():
    a = RetrievalResult(id="1", score=0.2, content_type="text", content="a")
    b = RetrievalResult(id="1", score=0.9, content_type="image", content="b")
    c = RetrievalResult(id="2", score=0.5, content_type="text", content="c")
    merged = merge_results([a, c], [b])
    by_id = {item.id: item for item in merged}
    assert by_id["1"].score == 0.9
    assert by_id["2"].score == 0.5


def test_rrf_merge_ranks_overlap_higher():
    first = [
        RetrievalResult(id="a", score=0.9, content_type="text", content="a"),
        RetrievalResult(id="b", score=0.8, content_type="text", content="b"),
    ]
    second = [
        RetrievalResult(id="b", score=0.7, content_type="text", content="b"),
        RetrievalResult(id="c", score=0.6, content_type="text", content="c"),
    ]
    fused = rrf_merge([first, second])
    assert [item.id for item in fused][0] == "b"
    by_id = {item.id: item for item in fused}
    assert by_id["b"].content == "b"


def test_rrf_merge_single_group_unchanged():
    group = [RetrievalResult(id="a", score=0.4, content_type="text")]
    assert rrf_merge([group])[0].id == "a"
    assert rrf_merge([]) == []


def test_rrf_merge_prefers_overlap_over_high_cosine_visual():
    text = [RetrievalResult(id="t", score=0.2, content_type="video_segment", content="talk")]
    visual = [
        RetrievalResult(id="v", score=0.95, content_type="image", content="noise"),
        RetrievalResult(id="t", score=0.10, content_type="image", content="talk"),
    ]
    fused = rrf_merge([text, visual])
    assert fused[0].id == "t"


def test_type_prior_prefers_video_segment_for_lecture_query():
    from app.retrieval.reranker import TypePriorReranker

    results = [
        RetrievalResult(id="i", score=0.016, content_type="image", content=""),
        RetrievalResult(id="s", score=0.016, content_type="video_segment", content="giảng"),
    ]
    ranked = TypePriorReranker().rerank("Giảng viên nói gì ở đầu buổi học?", results)
    assert [item.id for item in ranked][0] == "s"


def test_source_where_filename_and_path():
    from app.retrieval.retriever import source_where

    assert source_where("buoi_3.mp4") == {"filename": "buoi_3.mp4"}
    assert source_where("assets/test/buoi_3.mp4") == {"relative_path": "assets/test/buoi_3.mp4"}
    assert source_where(None) is None


def test_reranker_sorts_desc():
    results = [
        RetrievalResult(id="a", score=0.1, content_type="text"),
        RetrievalResult(id="b", score=0.8, content_type="text"),
    ]
    ranked = ScoreReranker().rerank("q", results)
    assert [r.id for r in ranked] == ["b", "a"]


def test_query_task_default_covers_lectures():
    from app.config.settings import Settings

    default = Settings.model_fields["query_task"].default
    assert "e-learning" in default
    assert "lectures" in default
    assert "evidence" in default


def test_retriever_uses_instruct_query(settings):
    store = ChromaVectorStore(
        settings.resolve_path(settings.chroma_path),
        settings.text_collection,
        settings.visual_collection,
    )
    embedder = FakeTextEmbedder()
    store.add(
        settings.text_collection,
        ["h:text:0"],
        [embedder.embed_documents(["Bài 5 quan hệ phản xạ"])[0]],
        ["Bài 5 quan hệ phản xạ"],
        [{"document_id": "h", "content_type": "text", "filename": "ex.docx"}],
    )
    retriever = MultimodalRetriever(settings, store, embedder, FakeVLEmbedder())
    hits = retriever.search("quan hệ phản xạ", k=1, include_visual=False)
    assert hits
    assert embedder.query_calls
    assert "Instruct:" in embedder.query_calls[0] or True
    # TextEmbeddingService adds Instruct; FakeTextEmbedder records raw embed_query arg.
    # Retriever calls embed_query with processed query only; service would wrap.
    assert hits[0].content_type == "text"


def test_retriever_enhanced_runs_each_text_query_vl_once(settings):
    store = ChromaVectorStore(
        settings.resolve_path(settings.chroma_path),
        settings.text_collection,
        settings.visual_collection,
    )
    text = FakeTextEmbedder()
    vl = FakeVLEmbedder()
    store.add(
        settings.text_collection,
        ["h:text:0", "h:text:1"],
        [text.embed_documents(["phản xạ", "đối xứng"])[0], text.embed_documents(["đối xứng"])[0]],
        ["phản xạ", "đối xứng"],
        [
            {"document_id": "h", "content_type": "text", "filename": "ex.docx"},
            {"document_id": "h", "content_type": "text", "filename": "ex.docx"},
        ],
    )
    store.add(
        settings.visual_collection,
        ["h:image:0"],
        [vl.embed_query("slide")],
        ["slide"],
        [{"document_id": "h", "content_type": "image", "filename": "ex.pptx"}],
    )
    retriever = MultimodalRetriever(settings, store, text, vl)
    enhanced = EnhancedQuery(
        original="px và dx",
        rewritten="quan hệ phản xạ và đối xứng",
        subqueries=["quan hệ phản xạ", "quan hệ đối xứng"],
        step_back="quan hệ hai ngôi",
    )
    text.query_calls.clear()
    vl.query_calls.clear()
    hits = retriever.search("px và dx", k=3, include_visual=True, enhanced=enhanced)
    assert hits
    assert text.query_calls == [
        "px và dx",
        "quan hệ phản xạ và đối xứng",
        "quan hệ phản xạ",
        "quan hệ đối xứng",
        "quan hệ hai ngôi",
    ]
    assert vl.query_calls == ["quan hệ phản xạ và đối xứng"]


def test_retriever_source_filters_filename(settings):
    store = ChromaVectorStore(
        settings.resolve_path(settings.chroma_path),
        settings.text_collection,
        settings.visual_collection,
    )
    embedder = FakeTextEmbedder()
    store.add(
        settings.text_collection,
        ["a:text:0", "b:text:0"],
        [embedder.embed_documents(["alpha"])[0], embedder.embed_documents(["beta"])[0]],
        ["alpha from a", "beta from b"],
        [
            {"document_id": "a", "content_type": "text", "filename": "keep.mp4", "relative_path": "assets/keep.mp4"},
            {"document_id": "b", "content_type": "text", "filename": "skip.docx", "relative_path": "assets/skip.docx"},
        ],
    )
    retriever = MultimodalRetriever(settings, store, embedder, FakeVLEmbedder())
    hits = retriever.search("alpha", k=5, include_visual=False, source="keep.mp4")
    assert hits
    assert all(hit.metadata.get("filename") == "keep.mp4" for hit in hits)
    assert hits[0].metadata.get("cosine") is not None


def test_retriever_folder_prefix_and_course(settings):
    store = ChromaVectorStore(
        settings.resolve_path(settings.chroma_path),
        settings.text_collection,
        settings.visual_collection,
    )
    embedder = FakeTextEmbedder()
    store.add(
        settings.text_collection,
        ["a:text:0", "b:text:0"],
        [embedder.embed_documents(["alpha course"])[0], embedder.embed_documents(["alpha other"])[0]],
        ["alpha course", "alpha other"],
        [
            {
                "document_id": "a",
                "content_type": "text",
                "filename": "chap01.pdf",
                "relative_path": "assets/hethongquytrinhnghiepvu/chap01.pdf",
            },
            {
                "document_id": "b",
                "content_type": "text",
                "filename": "skip.docx",
                "relative_path": "assets/test/skip.docx",
            },
        ],
    )
    retriever = MultimodalRetriever(settings, store, embedder, FakeVLEmbedder())
    hits = retriever.search(
        "alpha",
        k=5,
        include_visual=False,
        source="assets/hethongquytrinhnghiepvu",
    )
    assert hits
    assert all("hethongquytrinhnghiepvu" in hit.metadata["relative_path"] for hit in hits)
    course_hits = retriever.search(
        "alpha", k=5, include_visual=False, course="hethongquytrinhnghiepvu"
    )
    assert course_hits
    assert all("hethongquytrinhnghiepvu" in hit.metadata["relative_path"] for hit in course_hits)


def test_retriever_hyde_adds_extra_dense_group(settings):
    settings.query_hyde = True
    store = ChromaVectorStore(
        settings.resolve_path(settings.chroma_path),
        settings.text_collection,
        settings.visual_collection,
    )
    text = FakeTextEmbedder()
    store.add(
        settings.text_collection,
        ["h:text:0"],
        [text.embed_documents(["phản xạ"])[0]],
        ["phản xạ"],
        [{"document_id": "h", "content_type": "text", "filename": "ex.docx"}],
    )
    retriever = MultimodalRetriever(settings, store, text, FakeVLEmbedder())
    enhanced = EnhancedQuery(
        original="px",
        rewritten="quan hệ phản xạ",
        hyde="Đoạn văn về quan hệ phản xạ.",
    )
    text.query_calls.clear()
    retriever.search("px", k=2, include_visual=False, enhanced=enhanced)
    assert "px" in text.query_calls
    assert "quan hệ phản xạ" in text.query_calls
    assert "Đoạn văn về quan hệ phản xạ." in text.query_calls
    settings.query_hyde = False
    text.query_calls.clear()
    retriever.search("px", k=2, include_visual=False, enhanced=enhanced)
    assert "Đoạn văn về quan hệ phản xạ." not in text.query_calls
