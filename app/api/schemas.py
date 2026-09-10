from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

AssetKind = Literal["video", "pdf", "slide", "image", "document"]
StatusStage = Literal["enhancing", "retrieving", "generating"]


class Locator(BaseModel):
    page: int | None = None
    start_time: float | None = None
    end_time: float | None = None
    timestamp: float | None = None
    label: str | None = None


class Citation(BaseModel):
    id: str
    index: int
    content_type: str
    score: float
    title: str
    snippet: str = ""
    locator: Locator = Field(default_factory=Locator)
    asset_id: str


class Asset(BaseModel):
    id: str
    kind: AssetKind
    filename: str
    media_type: str
    download_url: str
    watch_url: str
    preview_url: str | None = None
    locators: list[Locator] = Field(default_factory=list)


class QueryPlan(BaseModel):
    rewritten: str
    subqueries: list[str] = Field(default_factory=list)
    step_back: str = ""


class AskRequest(BaseModel):
    query: str = Field(min_length=1)
    k: int | None = Field(default=None, ge=1, le=50)
    text_only: bool = True
    source: str | None = None
    enhance: bool | None = None
    stream: bool = True
    course: str | None = None
    content_type: str | None = None

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("query must not be empty")
        return value


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    k: int | None = Field(default=None, ge=1, le=50)
    text_only: bool = True
    source: str | None = None
    course: str | None = None
    content_type: str | None = None

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("query must not be empty")
        return value


class SearchResponse(BaseModel):
    hits: list[Citation]
    assets: list[Asset]


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    assets: list[Asset]
    query: QueryPlan | None = None


class HealthResponse(BaseModel):
    status: str = "ok"


class StatsResponse(BaseModel):
    text_collection: str
    text_count: int
    visual_collection: str
    visual_count: int
    chroma_path: str
    storage_root: str
    manifest: str
    device: str
    embedding: str
    llm_model: str


class SourcesPayload(BaseModel):
    citations: list[Citation]
    assets: list[Asset]


def dump_model(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
