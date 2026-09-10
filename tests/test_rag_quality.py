from app.generation.catalog import is_catalog_query, match_manifest_paths, merge_source_paths
from app.generation.context import format_hits
from app.generation.query_enhance import EnhancedQuery
from app.index_manifest import IndexManifest
from app.models.retrieval import RetrievalResult
from app.retrieval.compress import compress_hits
from app.retrieval.diversity import diversify_by_file
from app.retrieval.expand import expand_hits
from app.retrieval.filters import chroma_where, combine_where, folder_prefix
from app.retrieval.merger import rrf_merge
from app.retrieval.reranker import QwenReranker, SequentialReranker, TypePriorReranker, build_reranker
from app.retrieval.sparse import tokenize_query


def _hit(vec_id: str, *, path: str, content: str = "body", score: float = 0.5, **meta) -> RetrievalResult:
    metadata = {"relative_path": path, **meta}
    return RetrievalResult(
        id=vec_id,
        score=score,
        content_type=str(meta.get("content_type") or "text"),
        content=content,
        metadata=metadata,
    )


def test_combine_where_and():
    assert combine_where({"filename": "a.pdf"}, {"content_type": "text"}) == {
        "$and": [{"filename": "a.pdf"}, {"content_type": "text"}]
    }


def test_chroma_where_source_course_content_type():
    where = chroma_where("chap01.pdf", course="hethongquytrinhnghiepvu", content_type="text")
    assert where == {
        "$and": [
            {"filename": "chap01.pdf"},
            {"course": "hethongquytrinhnghiepvu"},
            {"content_type": "text"},
        ]
    }
    assert folder_prefix("hethongquytrinhnghiepvu") == "assets/hethongquytrinhnghiepvu"
    assert folder_prefix("assets/hethongquytrinhnghiepvu") == "assets/hethongquytrinhnghiepvu"
    assert folder_prefix("buoi_3.mp4") is None


def test_rrf_keeps_cosine_and_dedupes_ids():
    first = [
        _hit("a", path="assets/a.pdf", score=0.4, cosine=0.4),
        _hit("b", path="assets/b.pdf", score=0.3, cosine=0.3),
    ]
    second = [_hit("a", path="assets/a.pdf", score=5.0, cosine=0.2)]
    fused = rrf_merge([first, second])
    by_id = {item.id: item for item in fused}
    assert set(by_id) == {"a", "b"}
    assert by_id["a"].metadata["cosine"] == 0.4
    assert by_id["a"].score != 0.4


def test_bm25_exact_token():
    rank_bm25 = __import__("pytest").importorskip("rank_bm25")
    del rank_bm25
    from app.retrieval.sparse import BM25Index, _make_bm25

    assert tokenize_query("Quy trình nghiệp vụ") == ["quy", "trình", "nghiệp", "vụ"]
    index = BM25Index()
    index.ids = ["hit", "miss", "other"]
    index.documents = [
        "quy trình nghiệp vụ chap02",
        "toán rời rạc tập hợp",
        "an ninh mạng tường lửa",
    ]
    index.metadatas = [
        {"content_type": "text", "relative_path": "assets/hethongquytrinhnghiepvu/chap02.pdf"},
        {"content_type": "text", "relative_path": "assets/test/other.docx"},
        {"content_type": "text", "relative_path": "assets/test/sec.docx"},
    ]
    index._bm25 = _make_bm25([tokenize_query(doc) for doc in index.documents])
    hits = index.search("quy trình nghiệp vụ", k=2)
    assert hits
    assert hits[0].id == "hit"


def test_expand_joins_page_siblings():
    class Store:
        def get(self, collection, ids=None, where=None):
            assert collection == "text_embeddings"
            assert where == {"$and": [{"document_id": "doc"}, {"page_number": 3}]}
            return {
                "ids": ["a", "b"],
                "documents": ["first sentence.", "second sentence."],
                "metadatas": [{"chunk_index": 1}, {"chunk_index": 0}],
            }

    hits = [
        _hit(
            "child",
            path="assets/hethongquytrinhnghiepvu/chap01.pdf",
            content="first sentence.",
            document_id="doc",
            page_number=3,
            chunk_index=1,
            content_type="text",
        )
    ]
    expanded = expand_hits(hits, Store(), "text_embeddings")
    assert "first sentence." in expanded[0].content
    assert "second sentence." in expanded[0].content


def test_compress_keeps_overlapping_sentences():
    long = (
        "Câu này nói về quy trình nghiệp vụ của doanh nghiệp. " * 4
        + "Đây là một câu hoàn toàn lệch chủ đề toán học rời rạc. "
        + "Tài liệu chap02 mô tả quy trình nghiệp vụ chi tiết."
    )
    assert len(long) >= 240
    hits = [_hit("c", path="assets/x.pdf", content=long)]
    out = compress_hits(hits, "quy trình nghiệp vụ")
    assert "quy trình nghiệp vụ" in out[0].content
    assert "toán học rời rạc" not in out[0].content


def test_diversity_caps_per_file():
    hits = [
        _hit(f"c{i}", path="assets/hethongquytrinhnghiepvu/chap01.pdf", score=1 - i * 0.01)
        for i in range(7)
    ]
    hits.append(_hit("c8", path="assets/hethongquytrinhnghiepvu/chap08.pdf", score=0.2))
    out = diversify_by_file(hits, k=4, max_per_file=2)
    chap01 = [item for item in out if "chap01" in item.metadata["relative_path"]]
    assert len(chap01) <= 2
    assert any("chap08" in item.metadata["relative_path"] for item in out)


def test_format_hits_has_no_chunk_index():
    text = format_hits(
        [
            _hit(
                "h",
                path="assets/hethongquytrinhnghiepvu/chap01.pdf",
                content="mục lục",
                page_number=3,
                chunk_index=15,
            )
        ]
    )
    assert "chap01.pdf" in text
    assert "p.3" in text
    assert "#15" not in text
    assert "#1" not in text


def test_catalog_intent_and_manifest_paths(tmp_path):
    assert is_catalog_query("Tạo lộ trình môn quy trình nghiệp vụ, cho tôi tài liệu nếu có")
    manifest = IndexManifest(tmp_path / "manifest.json")
    manifest.record(
        "h1",
        relative_path="assets/hethongquytrinhnghiepvu/chap02.pdf",
        filename="chap02.pdf",
        file_type="pdf",
        content_types=["text"],
    )
    manifest.record(
        "h2",
        relative_path="assets/test/other.docx",
        filename="other.docx",
        file_type="docx",
        content_types=["text"],
    )
    paths = match_manifest_paths(
        manifest, "Tạo lộ trình môn quy trình nghiệp vụ, cho tôi tài liệu nếu có"
    )
    assert paths == ["assets/hethongquytrinhnghiepvu/chap02.pdf"]
    merged = merge_source_paths(
        [_hit("a", path="assets/hethongquytrinhnghiepvu/chap01.pdf")],
        paths,
    )
    assert "chap01.pdf" in merged
    assert "chap02.pdf" in merged


def test_original_first_in_text_search_queries():
    enhanced = EnhancedQuery(
        original="câu gốc",
        rewritten="câu viết lại",
        subqueries=["phụ 1"],
        step_back="bước lùi",
    )
    assert enhanced.text_search_queries()[0] == "câu gốc"


def test_build_reranker_default_is_type_prior(settings):
    settings.rerank_enabled = False
    assert isinstance(build_reranker(settings), TypePriorReranker)


def test_qwen_reranker_load_failure_keeps_order(monkeypatch):
    reranker = QwenReranker("Qwen/Qwen3-Reranker-0.6B")

    def boom(self):
        self._failed = True
        return False

    monkeypatch.setattr(QwenReranker, "_ensure_loaded", boom)
    items = [_hit("a", path="a.pdf", score=0.2), _hit("b", path="b.pdf", score=0.1)]
    assert [item.id for item in reranker.rerank("q", items)] == ["a", "b"]


def test_sequential_reranker_runs_type_prior_then_ce():
    class FakeCE:
        def rerank(self, query, results, *, source=None):
            return list(reversed(list(results)))

    items = [
        RetrievalResult(id="i", score=0.016, content_type="image", content=""),
        RetrievalResult(id="s", score=0.016, content_type="video_segment", content="giảng"),
    ]
    ranked = SequentialReranker(TypePriorReranker(), FakeCE()).rerank(
        "Giảng viên nói gì ở đầu buổi học?", items
    )
    assert ranked[0].id == "i"
    assert ranked[1].id == "s"
