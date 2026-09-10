from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config.settings import Settings
from app.ids import vector_id
from app.models.chunk import TextChunk


def chunk_params(
    settings: Settings | None,
    file_type: str | None,
    fallback_size: int = 500,
    fallback_overlap: int = 50,
) -> tuple[int, int]:
    if settings is not None:
        return settings.chunk_params(file_type)
    return fallback_size, fallback_overlap


class TextChunker:
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        settings: Settings | None = None,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.settings = settings
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def chunk_blocks(
        self,
        document_id: str,
        blocks: list[dict],
        *,
        content_type: str = "text",
        file_type: str | None = None,
    ) -> list[TextChunk]:
        size, overlap = chunk_params(
            self.settings, file_type, self.chunk_size, self.chunk_overlap
        )
        splitter = (
            self.splitter
            if (size, overlap) == (self.chunk_size, self.chunk_overlap)
            else RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap)
        )
        chunks: list[TextChunk] = []
        index = 0
        for block in blocks:
            text = (block.get("text") or "").strip()
            if not text:
                continue
            page = block.get("page_number")
            section = block.get("section")
            parts = splitter.split_text(text) if len(text) > size else [text]
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                chunks.append(
                    TextChunk(
                        id=vector_id(document_id, content_type, index),
                        document_id=document_id,
                        text=part,
                        page_number=page,
                        section=section,
                        chunk_index=index,
                    )
                )
                index += 1
        return chunks
