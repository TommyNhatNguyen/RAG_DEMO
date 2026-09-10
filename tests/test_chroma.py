from app.vectorstore.chroma import ChromaVectorStore, flatten_metadata


def test_flatten_drops_none_and_stringifies():
    meta = flatten_metadata({"a": "x", "b": None, "c": 1, "d": ["nope"]})
    assert meta["a"] == "x"
    assert "b" not in meta
    assert meta["c"] == 1
    assert meta["d"] == "['nope']"


def test_chroma_add_search_delete(settings):
    store = ChromaVectorStore(settings.resolve_path(settings.chroma_path), "text_embeddings", "visual_embeddings")
    added, skipped = store.add(
        "text_embeddings",
        ["hash:text:0"],
        [[0.1, 0.2, 0.3, 0.4]],
        ["hello world"],
        [{"document_id": "hash", "content_type": "text", "filename": "a.txt"}],
    )
    assert added == 1
    assert skipped == 0
    added2, skipped2 = store.add(
        "text_embeddings",
        ["hash:text:0"],
        [[0.1, 0.2, 0.3, 0.4]],
        ["hello world"],
        [{"document_id": "hash", "content_type": "text", "filename": "a.txt"}],
    )
    assert added2 == 0
    assert skipped2 == 1
    assert store.count("text_embeddings") == 1
    hits = store.search("text_embeddings", [0.1, 0.2, 0.3, 0.4], k=1)
    assert hits[0]["id"] == "hash:text:0"
    filtered = store.search(
        "text_embeddings",
        [0.1, 0.2, 0.3, 0.4],
        k=1,
        where={"filename": "a.txt"},
    )
    assert filtered[0]["id"] == "hash:text:0"
    missing = store.search(
        "text_embeddings",
        [0.1, 0.2, 0.3, 0.4],
        k=1,
        where={"filename": "nope.txt"},
    )
    assert missing == []
    assert store.has_document("text_embeddings", "hash")
    deleted = store.delete("text_embeddings", where={"document_id": "hash"})
    assert deleted == 1
    assert store.count("text_embeddings") == 0
