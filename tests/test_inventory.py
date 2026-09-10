from pathlib import Path

from app.eval.dashboard import render_dashboard
from app.eval.inventory import (
    CONTENT_TYPES,
    build_inventory,
    count_storage_images,
    count_vector_breakdown,
    format_inventory_vi,
    inventory_assets,
)
from app.main import build_parser
from tests.conftest import FakeTextEmbedder
from tests.test_incremental import _pipeline


class FakeStore:
    def __init__(self, payloads: dict[str, dict]):
        self.payloads = payloads

    def get(self, collection):
        return self.payloads.get(collection, {"ids": [], "metadatas": []})


def test_cli_no_video_inventory_report_flags():
    parser = build_parser()
    ingest = parser.parse_args(["ingest", "./assets", "--no-video"])
    assert ingest.no_video is True
    stats = parser.parse_args(["stats", "--detailed", "--out", "evals/reports/inventory.json"])
    assert stats.detailed is True
    assert stats.out == "evals/reports/inventory.json"
    inv = parser.parse_args(["inventory", "./assets", "--out", "evals/reports/assets-inventory.json"])
    assert inv.func.__name__ == "cmd_inventory"
    report = parser.parse_args(["report", "evals/reports/dashboard.html"])
    assert report.func.__name__ == "cmd_report"


def test_inventory_assets_walk(tmp_path: Path):
    assets = tmp_path / "assets"
    course = assets / "hethongquytrinhnghiepvu"
    course.mkdir(parents=True)
    (course / "chap01.pdf").write_bytes(b"%PDF-fake")
    (course / "notes.txt").write_text("hello")
    video = assets / "test"
    video.mkdir()
    (video / "buoi_3.mp4").write_bytes(b"fake-mp4")
    data = inventory_assets(assets, tmp_path)
    assert data["n_files"] == 3
    assert data["by_kind"]["document"] == 1
    assert data["by_kind"]["text"] == 1
    assert data["by_kind"]["video"] == 1
    assert data["by_suffix"]["pdf"] == 1
    assert data["by_suffix"]["mp4"] == 1
    assert data["by_course"]["hethongquytrinhnghiepvu"]["files"] == 2
    assert data["videos"][0]["ingest"] == "skip"
    assert data["videos"][0]["relative_path"].endswith("buoi_3.mp4")


def test_count_storage_images_page_vs_picture(tmp_path: Path):
    images = tmp_path / "images" / "doc1"
    images.mkdir(parents=True)
    (images / "page_1.png").write_bytes(b"png")
    (images / "page_2.png").write_bytes(b"png")
    (images / "picture_0.png").write_bytes(b"png")
    counted = count_storage_images(tmp_path)
    assert counted["page"] == 2
    assert counted["picture"] == 1
    assert counted["bytes"] > 0


def test_count_vector_breakdown_fake_metadatas():
    store = FakeStore(
        {
            "text_embeddings": {
                "ids": ["a", "b", "c"],
                "metadatas": [
                    {"content_type": "text", "file_type": "pdf", "course": "qt"},
                    {"content_type": "table", "file_type": "pdf", "course": "qt"},
                    {"content_type": "text", "file_type": "txt", "course": "oop"},
                ],
            },
            "visual_embeddings": {
                "ids": ["p", "i"],
                "metadatas": [
                    {"content_type": "page", "file_type": "pdf", "course": "qt"},
                    {"content_type": "image", "file_type": "pptx", "course": "qt"},
                ],
            },
        }
    )
    data = count_vector_breakdown(store, "text_embeddings", "visual_embeddings")
    assert data["text_count"] == 3
    assert data["visual_count"] == 2
    assert data["by_content_type"]["text"] == 2
    assert data["by_content_type"]["table"] == 1
    assert data["by_content_type"]["page"] == 1
    assert data["by_content_type"]["image"] == 1
    assert data["by_content_type"]["video_segment"] == 0
    assert data["by_content_type"]["video_frame"] == 0
    assert data["by_file_type"]["pdf"] == 3
    assert data["by_course"]["qt"] == 4
    for key in CONTENT_TYPES:
        assert key in data["by_content_type"]


def test_format_inventory_vi():
    data = build_inventory(
        assets={
            "n_files": 4,
            "bytes": 100,
            "by_kind": {"image": 0, "video": 1},
            "by_suffix": {"pdf": 2, "pptx": 0, "docx": 1, "txt": 1},
        },
        storage_images={"page": 10, "picture": 3, "other": 0, "bytes": 50},
        vectors={
            "text_count": 80,
            "visual_count": 12,
            "by_content_type": {
                "text": 70,
                "table": 10,
                "page": 8,
                "image": 4,
                "video_segment": 0,
                "video_frame": 0,
            },
        },
        chroma_path="data/chroma",
        storage_root="storage",
        manifest="data/index_manifest.json",
    )
    text = format_inventory_vi(data)
    assert "pdf=2" in text
    assert "video=1 (skipped)" in text
    assert "page=10" in text
    assert "text_collection=80" in text
    assert "video_segment=0" in text


def test_dashboard_html_contains_labels_and_numbers():
    html = render_dashboard(
        {
            "assets": {
                "n_files": 9,
                "bytes": 12345,
                "by_kind": {"document": 7, "video": 1, "text": 1},
                "by_suffix": {"pdf": 6, "pptx": 1, "docx": 1, "txt": 1},
                "by_course": {
                    "hethongquytrinhnghiepvu": {
                        "files": 8,
                        "bytes": 1000,
                        "by_kind": {"document": 7, "text": 1},
                    }
                },
                "videos": [
                    {
                        "relative_path": "assets/test/buoi_3.mp4",
                        "course": "test",
                        "bytes": 99,
                    }
                ],
            },
            "inventory": {
                "images": {"page": 40, "picture": 5, "bytes": 200},
                "vectors": {
                    "text_count": 200,
                    "visual_count": 45,
                    "by_content_type": {
                        "text": 180,
                        "table": 20,
                        "page": 40,
                        "image": 5,
                        "video_segment": 0,
                        "video_frame": 0,
                    },
                    "by_file_type": {"pdf": 210},
                    "by_course": {"hethongquytrinhnghiepvu": 200},
                },
                "flags": {"query_hyde": False, "max_retrieve_loops": 0, "no_video": True},
            },
            "fresh": {
                "n": 35,
                "scores": {
                    "path_recall": 0.8,
                    "path_precision": 0.4,
                    "path_recall_at_1": 0.5,
                    "path_recall_at_5": 0.7,
                    "path_recall_at_10": 0.8,
                },
                "by_kind": {
                    "video": {
                        "n": 3,
                        "path_recall": 0.0,
                        "path_precision": 0.0,
                        "path_recall_at_1": 0.0,
                        "path_recall_at_5": 0.0,
                        "path_recall_at_10": 0.0,
                    }
                },
                "weakest_metric": "path_precision",
                "next_step": "chunking / metadata filters",
            },
            "baseline": {
                "n": 35,
                "scores": {"path_recall": 0.975, "path_precision": 0.392},
                "weakest_metric": "path_precision",
            },
        }
    )
    assert "Tóm tắt thống kê" in html
    assert "PDF" in html
    assert "200" in html
    assert "QUERY_HYDE=false" in html
    assert "--no-video=true" in html
    assert "buoi_3.mp4" in html
    assert "path_precision" in html
    assert "cdn." not in html.lower()
    assert "<link rel" not in html


def test_ingest_no_video_skips_mp4(settings):
    embedder = FakeTextEmbedder()
    pipeline, store, _ = _pipeline(settings, embedder)

    class BoomLoader:
        def load(self, path, document_id):
            raise AssertionError("video loader should not run")

    pipeline.video_loader = BoomLoader()
    txt = settings.project_root / "notes.txt"
    txt.write_text("Quan he phan xa tren tap {1,2,3,4}. " * 8)
    mp4 = settings.project_root / "buoi_3.mp4"
    mp4.write_bytes(b"fake-mp4-bytes")
    report = pipeline.ingest(settings.project_root, no_video=True)
    assert report.counts()["skipped_video"] == 1
    assert report.counts()["indexed"] == 1
    assert store.count(settings.text_collection) >= 1
