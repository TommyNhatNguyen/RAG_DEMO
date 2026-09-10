from app.chunking.text_chunker import TextChunker


def test_chunker_preserves_section_and_page():
    chunker = TextChunker(chunk_size=40, chunk_overlap=5)
    blocks = [
        {"text": "Heading A", "page_number": 1, "section": "Heading A"},
        {
            "text": "This is a longer paragraph that should split into multiple chunks for testing.",
            "page_number": 1,
            "section": "Heading A",
        },
        {"text": "Page two text.", "page_number": 2, "section": "Heading B"},
    ]
    chunks = chunker.chunk_blocks("doc1", blocks)
    assert chunks
    assert chunks[0].document_id == "doc1"
    assert all(c.section in {"Heading A", "Heading B"} for c in chunks)
    assert any(c.page_number == 2 for c in chunks)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_chunk_params_per_type():
    from app.chunking.text_chunker import chunk_params
    from app.config.settings import Settings

    settings = Settings()
    assert settings.chunk_params("pdf") == (350, 60)
    assert settings.chunk_params("docx") == (350, 60)
    assert settings.chunk_params("pptx") == (280, 40)
    assert settings.chunk_params("txt") == (500, 50)
    assert settings.chunk_profile().startswith("pdf=350/60;docx=350/60;")
    assert chunk_params(settings, "pdf") == (350, 60)
    assert chunk_params(None, "pdf", 500, 50) == (500, 50)


def test_chunker_uses_pptx_size_when_settings_set():
    from app.config.settings import Settings

    settings = Settings(chunk_size_pptx=80, chunk_overlap_pptx=10)
    chunker = TextChunker(chunk_size=500, chunk_overlap=50, settings=settings)
    text = "slide word " * 40
    chunks = chunker.chunk_blocks("doc", [{"text": text, "page_number": 1}], file_type="pptx")
    assert len(chunks) > 1
