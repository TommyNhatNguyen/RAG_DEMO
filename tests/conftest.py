from __future__ import annotations

from pathlib import Path

import pytest

from app.config.settings import Settings


class FakeTextEmbedder:
    def __init__(self) -> None:
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    def embed_documents(self, texts, batch_size=None):
        self.document_calls.append(list(texts))
        return [_vec(text) for text in texts]

    def embed_query(self, text: str):
        self.query_calls.append(text)
        return _vec(text)


class FakeVLEmbedder:
    def __init__(self) -> None:
        self.image_calls: list[list] = []
        self.query_calls: list[str] = []

    def embed_images(self, inputs, batch_size=None):
        self.image_calls.append(list(inputs))
        return [_vec(str(item)) for item in inputs]

    def embed_query(self, text: str):
        self.query_calls.append(text)
        return _vec(text)


def _vec(text: str) -> list[float]:
    seed = float(len(str(text)) % 97)
    return [seed / 100.0, 0.2, 0.3, 0.4, 0.5, 0.1, 0.0, 0.8]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        project_root=tmp_path,
        chroma_path=tmp_path / "data" / "chroma",
        manifest_path=tmp_path / "data" / "index_manifest.json",
        storage_root=tmp_path / "storage",
        device="cpu",
        chunk_size=50,
        chunk_overlap=10,
        retriever_k=5,
        query_enhance=False,
        video_max_representative_frames=3,
        # Pin every env-tunable retrieval/generation toggle explicitly so
        # tests never inherit whatever a developer's local .env happens to
        # have set (e.g. an experiment run with QUERY_HYDE/MAX_RETRIEVE_LOOPS/
        # RERANK_ENABLED turned on) — pydantic-settings reads .env as the
        # default for any field not passed here.
        query_hyde=False,
        max_retrieve_loops=0,
        rerank_enabled=False,
    )
