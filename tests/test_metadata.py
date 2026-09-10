from app.pipeline.indexing import base_metadata
from app.models.document import DocumentAsset


def test_metadata_has_citation_fields():
    asset = DocumentAsset(
        id="abc",
        source="/tmp/assets/test/file.docx",
        file_name="file.docx",
        relative_path="assets/test/file.docx",
        file_type="docx",
    )
    meta = base_metadata(asset, content_type="text", chunk_index=2, extra={"page_number": 3})
    assert meta["document_id"] == "abc"
    assert meta["filename"] == "file.docx"
    assert meta["relative_path"] == "assets/test/file.docx"
    assert meta["content_type"] == "text"
    assert meta["chunk_index"] == 2
    assert meta["page_number"] == 3
    assert meta["course"] == "test"
    assert None not in meta.values()
