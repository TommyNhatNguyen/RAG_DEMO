import json

import pytest

from app.eval.retrieval_benchmark import (
    RetrievalInput,
    load_query_file,
    metrics_at_k,
    prepare_query_file,
    result_matches_evidence,
    run_retrieval,
    score_retrieval_file,
)
from app.models.retrieval import RetrievalResult


class RecordingRetriever:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def search(self, question, **kwargs):
        self.calls.append((question, kwargs))
        return self.hits


def _hit(path="assets/course/buoi_1/slide.pptx"):
    return RetrievalResult(
        id="doc:text:4",
        score=0.75,
        content_type="text",
        content="ignored",
        metadata={
            "relative_path": path,
            "file_type": "pptx",
            "page_number": 3,
            "document_id": "doc",
            "cosine": 0.75,
        },
    )


def test_prepare_queries_physically_removes_ground_truth(tmp_path):
    source = tmp_path / "questions.json"
    source.write_text(
        json.dumps(
            [
                {
                    "question": "Câu hỏi?",
                    "course_id": "course",
                    "answerable": True,
                    "evidence": [{"resource_id": "secret"}],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "queries.jsonl"
    assert prepare_query_file(source, output) == 1
    row = json.loads(output.read_text(encoding="utf-8"))
    assert row == {
        "question_id": "Q001",
        "question": "Câu hỏi?",
        "course_id": "course",
    }
    assert load_query_file(output) == [RetrievalInput("Q001", "Câu hỏi?", "course")]


def test_query_loader_rejects_ground_truth_fields(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(
        json.dumps(
            {
                "question_id": "Q001",
                "question": "q",
                "course_id": "c",
                "answerable": True,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="forbidden fields"):
        load_query_file(path)


def test_retrieval_output_has_required_fields_without_ground_truth(tmp_path):
    retriever = RecordingRetriever([_hit()])
    target = tmp_path / "results.jsonl"
    run_retrieval(
        retriever,
        [RetrievalInput("Q001", "Câu hỏi?", "course")],
        target,
        system_id="baseline",
        top_k=10,
        include_visual=False,
    )
    row = json.loads(target.read_text(encoding="utf-8"))
    assert "answerable" not in row and "evidence" not in row
    assert retriever.calls == [
        (
            "Câu hỏi?",
            {"k": 10, "include_visual": False, "course": "course"},
        )
    ]
    result = row["results"][0]
    assert result["question_id"] == "Q001"
    assert result["rank"] == 1
    assert result["resource_id"] == "RAG_DEMO/assets/course/buoi_1/slide.pptx"
    assert result["resource_type"] == "slide"
    assert result["chunk_id"] == "doc:text:4"
    assert result["slide"] == 3


def test_metrics_use_fixed_k_and_unique_ground_truth_recall():
    evidence = [
        {"resource_id": "RAG_DEMO/assets/a.pdf", "page": 2, "slide": None, "timestamp": None},
        {"resource_id": "RAG_DEMO/assets/b.pdf", "page": 4, "slide": None, "timestamp": None},
    ]
    results = [
        {"resource_id": "assets/a.pdf", "page": 2, "slide": None, "start_time": None, "end_time": None},
        {"resource_id": "assets/a.pdf", "page": 2, "slide": None, "start_time": None, "end_time": None},
        {"resource_id": "assets/x.pdf", "page": 1, "slide": None, "start_time": None, "end_time": None},
    ]
    at_1 = metrics_at_k(evidence, results, 1)
    assert at_1["precision"] == 1.0
    assert at_1["recall"] == 0.5
    assert at_1["f1"] == pytest.approx(2 / 3)
    at_5 = metrics_at_k(evidence, results, 5)
    assert at_5["precision"] == 2 / 5
    assert at_5["recall"] == 0.5


def test_video_match_uses_time_overlap():
    evidence = {
        "resource_id": "RAG_DEMO/assets/course/a.mp4",
        "page": None,
        "slide": None,
        "timestamp": "00:01:00.5–00:01:20",
    }
    assert result_matches_evidence(
        {
            "resource_id": "assets/course/a.mp4",
            "start_time": 50.0,
            "end_time": 65.0,
            "page": None,
            "slide": None,
        },
        evidence,
    )
    assert not result_matches_evidence(
        {
            "resource_id": "assets/course/a.mp4",
            "start_time": 20.0,
            "end_time": 30.0,
            "page": None,
            "slide": None,
        },
        evidence,
    )


def test_unanswerable_is_separate_and_never_divides_by_zero(tmp_path):
    questions = tmp_path / "questions.json"
    questions.write_text(
        json.dumps(
            [
                {
                    "question": "answerable",
                    "course_id": "c",
                    "answerable": None,
                    "evidence": [
                        {
                            "resource_id": "RAG_DEMO/assets/a.pdf",
                            "page": 1,
                            "slide": None,
                            "timestamp": None,
                        }
                    ],
                },
                {
                    "question": "unanswerable",
                    "course_id": "c",
                    "answerable": None,
                    "evidence": [],
                },
            ]
        ),
        encoding="utf-8",
    )
    results = tmp_path / "results.jsonl"
    rows = [
        {
            "question_id": "Q001",
            "system_id": "test",
            "results": [
                {
                    "resource_id": "assets/a.pdf",
                    "page": 1,
                    "slide": None,
                    "start_time": None,
                    "end_time": None,
                }
            ],
        },
        {"question_id": "Q002", "system_id": "test", "results": []},
    ]
    results.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    report = score_retrieval_file(questions, results, null_policy="infer")
    assert report["counts"]["answerable_scored"] == 1
    assert report["counts"]["unanswerable_separate"] == 1
    assert report["macro_average_answerable"]["recall@1"] == 1.0
    assert report["unanswerable_evaluation"]["retrieval_precision_recall_f1"] is None
    assert report["unanswerable_evaluation"]["rejection_rate"] is None


def test_missing_indexed_ground_truth_is_excluded_from_macro(tmp_path):
    questions = tmp_path / "questions.json"
    questions.write_text(
        json.dumps(
            [
                {
                    "question": "available",
                    "answerable": True,
                    "evidence": [{"resource_id": "RAG_DEMO/assets/a.pdf", "page": 1}],
                },
                {
                    "question": "missing",
                    "answerable": True,
                    "evidence": [{"resource_id": "RAG_DEMO/assets/b.pdf", "page": 1}],
                },
            ]
        ),
        encoding="utf-8",
    )
    results = tmp_path / "results.jsonl"
    rows = [
        {
            "question_id": "Q001",
            "system_id": "test",
            "results": [{"resource_id": "assets/a.pdf", "page": 1}],
        },
        {"question_id": "Q002", "system_id": "test", "results": []},
    ]
    results.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    report = score_retrieval_file(
        questions,
        results,
        indexed_resource_ids={"RAG_DEMO/assets/a.pdf"},
    )
    assert report["counts"]["answerable_scored"] == 1
    assert report["counts"]["answerable_unscorable_missing_index"] == 1
    assert report["corpus_coverage"]["rate"] == 0.5
    assert report["macro_average_answerable"]["recall@1"] == 1.0
