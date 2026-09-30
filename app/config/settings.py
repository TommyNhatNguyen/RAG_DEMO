from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    project_root: Path = Field(default_factory=lambda: Path.cwd())

    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    vl_embedding_model: str = "Qwen/Qwen3-VL-Embedding-2B"

    chroma_path: Path = Path("./data/chroma")
    text_collection: str = "text_embeddings"
    visual_collection: str = "visual_embeddings"
    manifest_path: Path = Path("./data/index_manifest.json")
    storage_root: Path = Path("./storage")

    ocr_engine: str = "tesseract"
    ocr_required: bool = False

    video_segment_duration: float = 30.0
    video_frames_per_segment: int = 3
    whisper_model: str = "base"
    whisper_compute_type: str = "int8"
    whisper_language: str | None = "vi"
    video_max_duration: float | None = None
    video_coarse_sample_interval: float = 10.0
    video_max_representative_frames: int = 3
    video_frame_similarity_threshold: float = 0.90
    video_ocr_enabled: bool = True
    video_ocr_interval: float = 30.0
    video_scene_enabled: bool = False
    video_scene_threshold: float = 27.0
    video_visual_change_weight: float = 0.35
    video_ocr_change_weight: float = 0.30
    video_scene_boundary_weight: float = 0.20
    video_temporal_coverage_weight: float = 0.15

    chunk_size: int = 500
    chunk_overlap: int = 50
    chunk_size_pdf: int = 350
    chunk_overlap_pdf: int = 60
    chunk_size_docx: int = 350
    chunk_overlap_docx: int = 60
    chunk_size_pptx: int = 280
    chunk_overlap_pptx: int = 40
    chunk_size_txt: int = 500
    chunk_overlap_txt: int = 50

    device: str = "mps"
    text_batch_size: int = 8
    vl_batch_size: int = 1
    retriever_k: int = 5
    generation_k: int = 8
    retriever_fetch_k: int = 20
    retrieve_max_per_file: int = 2
    cosine_fallback_threshold: float = 0.15
    course_prefilter: bool = False

    hybrid_search: bool = True
    bm25_path: Path = Path("./data/bm25.pkl")
    rerank_enabled: bool = False
    rerank_model: str = "Qwen/Qwen3-Reranker-0.6B"
    context_expand: bool = True
    context_compress: bool = True
    query_hyde: bool = False
    max_retrieve_loops: int = 0

    llm_model: str = "Qwen/Qwen3-1.7B"
    llm_max_new_tokens: int = 4096
    llm_enable_thinking: bool = False
    llm_max_context_chars: int = 10000
    llm_do_sample: bool = False

    vl_llm_model: str = "Qwen/Qwen3-VL-2B-Instruct"
    vl_llm_max_new_tokens: int = 768
    vl_max_images: int = 3

    query_enhance: bool = True
    query_enhance_max_subqueries: int = 3
    query_enhance_max_new_tokens: int = 256

    query_task: str = (
        "Given a learner question about an e-learning course "
        "(lectures, slides, transcripts, exercises, images, tables, formulas), "
        "retrieve relevant course materials that help answer with evidence"
    )

    hf_token: str | None = None
    hugging_face_hub_token: str | None = None

    generate_page_images: bool = True
    generate_picture_images: bool = True
    log_level: str = "INFO"

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_cors_origins: str = "*"
    api_key: str | None = None

    @field_validator(
        "hf_token",
        "hugging_face_hub_token",
        "video_max_duration",
        "api_key",
        "whisper_language",
        mode="before",
    )
    @classmethod
    def empty_to_none(cls, value):
        if value == "":
            return None
        return value

    def resolved_token(self) -> str | None:
        token = self.hf_token or self.hugging_face_hub_token
        if token:
            token = token.strip()
        return token or None

    def resolve_path(self, path: Path) -> Path:
        if path.is_absolute():
            return path
        return (self.project_root / path).resolve()

    def chunk_params(self, file_type: str | None) -> tuple[int, int]:
        kind = (file_type or "").lower().lstrip(".")
        if kind == "pdf":
            return self.chunk_size_pdf, self.chunk_overlap_pdf
        if kind == "docx":
            return self.chunk_size_docx, self.chunk_overlap_docx
        if kind in {"pptx", "ppt"}:
            return self.chunk_size_pptx, self.chunk_overlap_pptx
        if kind in {"txt", "md", "markdown"}:
            return self.chunk_size_txt, self.chunk_overlap_txt
        return self.chunk_size, self.chunk_overlap

    def chunk_profile(self) -> str:
        pdf_s, pdf_o = self.chunk_params("pdf")
        docx_s, docx_o = self.chunk_params("docx")
        pptx_s, pptx_o = self.chunk_params("pptx")
        txt_s, txt_o = self.chunk_params("txt")
        return (
            f"pdf={pdf_s}/{pdf_o};docx={docx_s}/{docx_o};"
            f"pptx={pptx_s}/{pptx_o};txt={txt_s}/{txt_o}"
        )


def resolve_device(preferred: str) -> str:
    preferred = (preferred or "cpu").lower()
    try:
        import torch
    except ImportError:
        return "cpu"

    if preferred == "mps":
        if torch.backends.mps.is_available() and torch.backends.mps.is_built():
            return "mps"
        return "cpu"
    if preferred == "cuda":
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"
    if preferred == "cpu":
        return "cpu"
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
