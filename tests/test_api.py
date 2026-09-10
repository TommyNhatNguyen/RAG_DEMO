from __future__ import annotations

import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.citations import hits_to_citations_and_assets
from app.generation.service import GenerationService
from app.models.retrieval import RetrievalResult
from app.retrieval.retriever import process_user_query


class FakeVectorStore:
    def count(self, collection: str) -> int:
        return 4 if "text" in collection else 2


class FakeRetriever:
    def __init__(self, hits: list[RetrievalResult] | None = None) -> None:
        self.hits = hits or []
        self.calls: list[tuple] = []

    def search(self, raw_query: str, k=None, include_visual=True, *, enhanced=None, source=None, course=None, content_type=None):
        self.calls.append((raw_query, k, include_visual, enhanced, source, course, content_type))
        if not process_user_query(raw_query):
            raise ValueError("Empty query after processing.")
        return self.hits


class FakeChatModel:
    def __init__(self, text: str = "final answer", chunks: list[str] | None = None) -> None:
        self.text = text
        self.chunks = chunks if chunks is not None else [text]
        self.invoked: list = []
        self.streamed: list = []

    def invoke(self, payload):
        self.invoked.append(payload)
        return self.text

    def stream(self, payload):
        self.streamed.append(payload)
        yield from self.chunks


def _hits() -> list[RetrievalResult]:
    return [
        RetrievalResult(
            id="1",
            score=0.9,
            content_type="text",
            content="Quan hệ phản xạ trên tập {1,2,3,4}",
            metadata={
                "relative_path": "assets/test/bai_tap_chuong_3.docx",
                "filename": "bai_tap_chuong_3.docx",
            },
        )
    ]


class FakeVectorStore:
    def count(self, collection: str) -> int:
        return 4 if "text" in collection else 2


def _client(settings, hits=None, chunks=None):
    retriever = FakeRetriever(hits if hits is not None else _hits())
    generator = GenerationService(
        settings,
        retriever,
        chat_model=FakeChatModel(chunks=chunks or ["xin ", "chào"]),
    )
    services = SimpleNamespace(
        generator=generator,
        retriever=retriever,
        vector_store=FakeVectorStore(),
    )
    app = create_app(settings=settings, services=services)
    return TestClient(app), generator, retriever


def _sse_events(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    name = "message"
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            name = line[len("event:") :].strip()
            continue
        if line.startswith("data:"):
            payload = json.loads(line[len("data:") :].strip() or "{}")
            events.append((name, payload))
            name = "message"
    return events


def test_health(settings):
    client, _, _ = _client(settings)
    with client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_stats(settings):
    client, _, _ = _client(settings)
    with client:
        response = client.get("/v1/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["text_count"] == 4
    assert body["visual_count"] == 2
    assert body["llm_model"] == settings.llm_model


def test_search_returns_assets_watch_url(settings):
    hits = [
        RetrievalResult(
            id="v1",
            score=0.81,
            content_type="video_segment",
            content="Giảng viên nhắc lại định nghĩa quan hệ phản xạ",
            metadata={
                "relative_path": "assets/test/buoi_3.mp4",
                "filename": "buoi_3.mp4",
                "file_type": "mp4",
                "start_time": 120.0,
                "end_time": 150.0,
            },
        )
    ]
    client, _, _ = _client(settings, hits=hits)
    with client:
        response = client.post("/v1/search", json={"query": "quan hệ", "text_only": True})
    assert response.status_code == 200
    body = response.json()
    assert body["hits"][0]["title"] == "buoi_3.mp4"
    assert body["assets"][0]["kind"] == "video"
    assert body["assets"][0]["download_url"] == "/v1/files/assets/test/buoi_3.mp4"
    assert body["assets"][0]["watch_url"] == "/v1/files/assets/test/buoi_3.mp4#t=120,150"


def test_ask_sse_delta_and_sources(settings):
    client, _, _ = _client(settings)
    with client:
        response = client.post(
            "/v1/ask",
            json={"query": "quan hệ", "text_only": True, "enhance": False},
        )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    events = _sse_events(response.text)
    names = [name for name, _ in events]
    assert "sources" in names
    assert "delta" in names
    assert names[-1] == "done"
    sources = next(payload for name, payload in events if name == "sources")
    assert sources["assets"][0]["download_url"].startswith("/v1/files/")
    text = "".join(payload["text"] for name, payload in events if name == "delta")
    assert text == "xin chào"


def test_empty_query_422(settings):
    client, _, _ = _client(settings)
    with client:
        blank = client.post("/v1/ask", json={"query": ""})
        spaces = client.post("/v1/ask", json={"query": "   "})
        search_blank = client.post("/v1/search", json={"query": ""})
    assert blank.status_code == 422
    assert spaces.status_code == 422
    assert search_blank.status_code == 422


def test_search_passes_course_and_content_type(settings):
    client, _, retriever = _client(settings)
    with client:
        response = client.post(
            "/v1/search",
            json={
                "query": "quan hệ",
                "course": "hethongquytrinhnghiepvu",
                "content_type": "text",
            },
        )
    assert response.status_code == 200
    assert retriever.calls[0][5] == "hethongquytrinhnghiepvu"
    assert retriever.calls[0][6] == "text"


def test_ask_json_passes_course(settings):
    client, _, retriever = _client(settings)
    with client:
        response = client.post(
            "/v1/ask",
            json={
                "query": "quan hệ",
                "text_only": True,
                "enhance": False,
                "stream": False,
                "course": "test",
            },
        )
    assert response.status_code == 200
    assert retriever.calls[0][5] == "test"


def test_ask_stream_false_json(settings):
    client, _, _ = _client(settings, chunks=["final answer"])
    with client:
        response = client.post(
            "/v1/ask",
            json={
                "query": "quan hệ",
                "text_only": True,
                "enhance": False,
                "stream": False,
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "final answer"
    assert body["citations"]
    assert body["assets"]
    assert body["assets"][0]["download_url"].startswith("/v1/files/")


def test_files_sandbox(settings, tmp_path):
    settings.project_root = tmp_path
    settings.storage_root = tmp_path / "storage"
    assets = tmp_path / "assets" / "test"
    assets.mkdir(parents=True)
    (assets / "note.txt").write_text("hello", encoding="utf-8")
    frames = tmp_path / "storage" / "frames"
    frames.mkdir(parents=True)
    (frames / "shot.jpg").write_bytes(b"\xff\xd8\xff")
    secret = tmp_path / "secret.txt"
    secret.write_text("nope", encoding="utf-8")
    client, _, _ = _client(settings)
    with client:
        ok_asset = client.get("/v1/files/assets/test/note.txt")
        ranged = client.get(
            "/v1/files/assets/test/note.txt",
            headers={"Range": "bytes=0-3"},
        )
        ok_storage = client.get("/v1/files/storage/frames/shot.jpg")
        missing = client.get("/v1/files/assets/missing.txt")
        escape = client.get("/v1/files/../secret.txt")
        outside = client.get("/v1/files/secret.txt")
    assert ok_asset.status_code == 200
    assert ok_asset.content == b"hello"
    assert ranged.status_code == 206
    assert ranged.content == b"hell"
    assert ok_storage.status_code == 200
    assert missing.status_code == 404
    assert escape.status_code == 404
    assert outside.status_code == 404


def test_api_key_protects_v1_not_health_or_files(settings, tmp_path):
    settings.api_key = "secret"
    settings.project_root = tmp_path
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "a.txt").write_text("x", encoding="utf-8")
    client, _, _ = _client(settings)
    with client:
        denied = client.get("/v1/stats")
        allowed = client.get("/v1/stats", headers={"X-API-Key": "secret"})
        health = client.get("/health")
        file_ok = client.get("/v1/files/assets/a.txt")
    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert health.status_code == 200
    assert file_ok.status_code == 200


def test_hits_to_assets_pdf_and_preview(settings, tmp_path):
    settings.storage_root = tmp_path / "storage"
    preview = tmp_path / "storage" / "images" / "p.jpg"
    preview.parent.mkdir(parents=True)
    preview.write_bytes(b"x")
    hits = [
        RetrievalResult(
            id="p1",
            score=0.7,
            content_type="text",
            content="Định nghĩa quan hệ",
            metadata={
                "relative_path": "assets/hethongquytrinhnghiepvu/chap01.pdf",
                "filename": "chap01.pdf",
                "file_type": "pdf",
                "page_number": 3,
            },
        ),
        RetrievalResult(
            id="img",
            score=0.6,
            content_type="page",
            content="",
            metadata={
                "relative_path": "assets/test/Chuong_3_quan_he.pptx",
                "filename": "Chuong_3_quan_he.pptx",
                "file_type": "pptx",
                "page_number": 2,
                "image_path": str(preview),
            },
        ),
    ]
    _, assets = hits_to_citations_and_assets(hits, settings=settings)
    by_kind = {item.kind: item for item in assets}
    assert by_kind["pdf"].watch_url.endswith("#page=3")
    assert by_kind["slide"].preview_url == "/v1/files/storage/images/p.jpg"
    assert by_kind["slide"].watch_url == "/v1/files/storage/images/p.jpg"
