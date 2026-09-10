from pathlib import Path

from app.eval.golden import load_golden
from app.eval.judge import parse_judge_scores
from app.eval.metrics import path_precision_at_k, path_recall_at_k, weakest_metric
from app.eval.report import build_report, format_report
from app.eval.runner import run_eval
from app.generation.service import GenerationService
from app.main import build_parser
from app.models.retrieval import RetrievalResult
from app.retrieval.retriever import process_user_query


class FakeRetriever:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def search(self, raw_query, k=None, include_visual=True, *, enhanced=None, source=None, course=None, content_type=None):
        self.calls.append((raw_query, k, include_visual, enhanced, source, course, content_type))
        if not process_user_query(raw_query):
            raise ValueError("Empty query after processing.")
        return self.hits


class FakeChat:
    def invoke(self, payload):
        return (
            '{"faithfulness":0.9,"answer_relevancy":0.8,'
            '"context_precision":0.7,"context_recall":0.6,"completeness":4}'
        )


def _hit(path: str) -> RetrievalResult:
    return RetrievalResult(
        id=path,
        score=0.4,
        content_type="text",
        content="Quan hệ phản xạ trên tập {1,2,3,4}",
        metadata={"relative_path": path, "cosine": 0.4},
    )


def test_load_golden_skips_comments(tmp_path):
    path = tmp_path / "golden.jsonl"
    path.write_text(
        "# comment\n"
        '{"id":"a","question":"q1","ground_truth":"gt","expected_paths":["assets/a.pdf"]}\n'
        "\n",
        encoding="utf-8",
    )
    items = load_golden(path)
    assert len(items) == 1
    assert items[0].id == "a"
    assert items[0].expected_paths == ["assets/a.pdf"]


def test_path_recall_precision():
    hits = [
        _hit("assets/hethongquytrinhnghiepvu/chap01.pdf"),
        _hit("assets/hethongquytrinhnghiepvu/chap01.pdf"),
        _hit("assets/hethongquytrinhnghiepvu/chap02.pdf"),
    ]
    expected = [
        "assets/hethongquytrinhnghiepvu/chap01.pdf",
        "assets/hethongquytrinhnghiepvu/chap02.pdf",
        "assets/hethongquytrinhnghiepvu/chap03.pdf",
    ]
    assert path_recall_at_k(expected, hits) == 2 / 3
    assert path_precision_at_k(expected, hits) == 1.0
    assert path_recall_at_k(expected, hits, 1) == 1 / 3
    assert path_recall_at_k(expected, hits, 5) == 2 / 3
    assert path_recall_at_k(expected, hits, 10) == 2 / 3


def test_weakest_metric_prefers_llm_then_path():
    assert weakest_metric({"faithfulness": 0.9, "context_recall": 0.2, "context_precision": 0.5}) == "context_recall"
    assert weakest_metric({"path_recall": 0.1, "path_precision": 0.9}) == "path_recall"


def test_eval_cli_flags():
    parser = build_parser()
    args = parser.parse_args(
        ["eval", "evals/golden.jsonl", "--retrieve-only", "--limit", "5", "--out", "evals/reports/baseline.json"]
    )
    assert args.func.__name__ == "cmd_eval"
    assert args.retrieve_only is True
    assert args.limit == 5
    assert args.text_only is True
    visual = parser.parse_args(["eval", "evals/golden.jsonl", "--with-visual"])
    assert visual.text_only is False
    ingest = parser.parse_args(["ingest", "./assets", "--rechunk"])
    assert ingest.rechunk is True
    no_video = parser.parse_args(["ingest", "./assets", "--no-video"])
    assert no_video.no_video is True


def test_run_eval_retrieve_only_with_fakes(settings):
    hits = [_hit("assets/test/bai_tap_chuong_3.docx")]
    retriever = FakeRetriever(hits)
    generator = GenerationService(settings, retriever, chat_model=FakeChat())
    services = type("S", (), {"retriever": retriever, "generator": generator})()
    from app.eval.golden import GoldenItem

    items = [
        GoldenItem(
            id="ex1",
            question="quan hệ phản xạ",
            ground_truth="Quan hệ phản xạ trên tập {1,2,3,4}",
            kind="exercise",
            expected_paths=["assets/test/bai_tap_chuong_3.docx"],
        )
    ]
    report = run_eval(services, items, retrieve_only=True, enhance=False)
    assert report["n"] == 1
    assert report["scores"]["path_recall"] == 1.0
    assert report["scores"]["path_recall_at_1"] == 1.0
    assert report["scores"]["path_recall_at_5"] == 1.0
    assert report["scores"]["path_recall_at_10"] == 1.0
    assert report["scores"]["faithfulness"] is None
    assert "path_recall=1.000" in format_report(report)
    assert "path_recall_at_1=1.000" in format_report(report)


def test_run_eval_generate_uses_local_judge(settings, monkeypatch):
    hits = [_hit("assets/test/bai_tap_chuong_3.docx")]
    retriever = FakeRetriever(hits)
    generator = GenerationService(settings, retriever, chat_model=FakeChat())
    services = type("S", (), {"retriever": retriever, "generator": generator, "text_embedder": None})()

    def boom(*_a, **_k):
        return {}

    monkeypatch.setattr("app.eval.runner.score_with_ragas", boom)
    from app.eval.golden import GoldenItem

    items = [
        GoldenItem(
            id="ex1",
            question="quan hệ phản xạ",
            ground_truth="Quan hệ phản xạ trên tập {1,2,3,4}",
            kind="exercise",
            expected_paths=["assets/test/bai_tap_chuong_3.docx"],
        )
    ]
    report = run_eval(services, items, retrieve_only=False, enhance=False, use_ragas=True)
    assert report["scores"]["faithfulness"] == 0.9
    assert report["weakest_metric"] == "context_recall"


def test_parse_judge_scores():
    scores = parse_judge_scores(
        '{"faithfulness":1.2,"answer_relevancy":0.5,"context_precision":0.4,"context_recall":0.3,"completeness":9}'
    )
    assert scores["faithfulness"] == 1.0
    assert scores["completeness"] == 5.0


def test_build_report_faithfulness_warning():
    traces = [
        {
            "id": "a",
            "kind": "theory",
            "path_recall": 1.0,
            "path_precision": 1.0,
        }
    ]
    report = build_report(traces, llm_means={"faithfulness": 0.5, "context_precision": 0.9})
    assert report["warnings"]
    assert report["weakest_metric"] == "faithfulness"


def test_shipped_golden_has_enough_kinds():
    path = Path("evals/golden.jsonl")
    items = load_golden(path)
    assert len(items) >= 30
    kinds = {item.kind for item in items}
    assert {"catalog", "theory", "exercise", "slide", "table", "video"} <= kinds
