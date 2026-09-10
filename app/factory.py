from __future__ import annotations

import logging
from dataclasses import dataclass

from app.chunking.text_chunker import TextChunker
from app.config.settings import Settings
from app.embeddings.text_embedding import TextEmbeddingService
from app.embeddings.vl_embedding import VLEmbeddingService
from app.generation.service import GenerationService
from app.index_manifest import IndexManifest
from app.loaders.docling_loader import DoclingLoader
from app.loaders.image_loader import ImageLoader
from app.loaders.text_loader import TextLoader
from app.loaders.video_loader import VideoLoader
from app.pipeline.indexing import IndexingService
from app.pipeline.ingestion import IngestionPipeline
from app.processors.ocr import NullOCR, TesseractOCR
from app.retrieval.retriever import MultimodalRetriever
from app.retrieval.reranker import build_reranker
from app.storage.local import LocalFilesystemStore
from app.vectorstore.chroma import ChromaVectorStore

logger = logging.getLogger(__name__)


@dataclass
class AppServices:
    settings: Settings
    vector_store: ChromaVectorStore
    object_store: LocalFilesystemStore
    manifest: IndexManifest
    text_embedder: TextEmbeddingService
    vl_embedder: VLEmbeddingService
    pipeline: IngestionPipeline
    retriever: MultimodalRetriever
    generator: GenerationService


def login_hub(settings: Settings) -> None:
    token = settings.resolved_token()
    if not token:
        return
    from huggingface_hub import login

    login(token=token, add_to_git_credential=False)
    logger.info("Authenticated to Hugging Face Hub from env token")


def build_services(settings: Settings) -> AppServices:
    login_hub(settings)
    chroma_path = settings.resolve_path(settings.chroma_path)
    storage_root = settings.resolve_path(settings.storage_root)
    manifest_path = settings.resolve_path(settings.manifest_path)

    vector_store = ChromaVectorStore(
        persist_path=chroma_path,
        text_collection=settings.text_collection,
        visual_collection=settings.visual_collection,
    )
    object_store = LocalFilesystemStore(storage_root)
    manifest = IndexManifest(manifest_path)
    text_embedder = TextEmbeddingService(settings)
    vl_embedder = VLEmbeddingService(settings)

    ocr = TesseractOCR() if settings.ocr_engine.lower() == "tesseract" else NullOCR()
    text_chunker = TextChunker(
        settings.chunk_size, settings.chunk_overlap, settings=settings
    )
    docling_loader = DoclingLoader(settings, object_store, ocr)
    image_loader = ImageLoader(settings.project_root, object_store, ocr)
    video_loader = VideoLoader(settings, object_store, ocr=ocr)
    indexer = IndexingService(settings, vector_store, text_embedder, vl_embedder)
    pipeline = IngestionPipeline(
        settings=settings,
        vector_store=vector_store,
        object_store=object_store,
        manifest=manifest,
        indexer=indexer,
        text_chunker=text_chunker,
        docling_loader=docling_loader,
        image_loader=image_loader,
        text_loader=TextLoader(settings.project_root),
        video_loader=video_loader,
    )
    retriever = MultimodalRetriever(
        settings=settings,
        vector_store=vector_store,
        text_embedder=text_embedder,
        vl_embedder=vl_embedder,
        reranker=build_reranker(settings),
    )
    generator = GenerationService(
        settings=settings, retriever=retriever, manifest=manifest
    )
    return AppServices(
        settings=settings,
        vector_store=vector_store,
        object_store=object_store,
        manifest=manifest,
        text_embedder=text_embedder,
        vl_embedder=vl_embedder,
        pipeline=pipeline,
        retriever=retriever,
        generator=generator,
    )
