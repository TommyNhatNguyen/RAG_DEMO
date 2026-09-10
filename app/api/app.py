from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from app.api.citations import hits_to_citations_and_assets
from app.api.deps import get_services, get_settings, require_api_key
from app.api.files import router as files_router
from app.api.schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    QueryPlan,
    SearchRequest,
    SearchResponse,
    StatsResponse,
    dump_model,
)
from app.api.sse import sse_event
from app.config.settings import Settings
from app.factory import AppServices, build_services
from app.generation.query_enhance import EnhancedQuery
from app.generation.service import AskEvent
from app.log_setup import setup_logging

logger = logging.getLogger(__name__)
_SENTINEL = object()


def create_app(
    *,
    settings: Settings | None = None,
    services: AppServices | None = None,
) -> FastAPI:
    cfg = settings

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved = cfg or Settings()
        setup_logging(resolved.log_level)
        app.state.settings = resolved
        app.state.services = (
            services if services is not None else build_services(resolved)
        )
        app.state.inference_lock = asyncio.Lock()
        yield

    cors_settings = cfg or Settings()
    origins = _cors_origins(cors_settings.api_cors_origins)
    app = FastAPI(
        title="Multimodal RAG e-learning API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(files_router)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    v1 = APIRouter(prefix="/v1", dependencies=[Depends(require_api_key)])

    @v1.get("/stats", response_model=StatsResponse)
    def stats(
        svc: AppServices = Depends(get_services),
        app_settings: Settings = Depends(get_settings),
    ) -> StatsResponse:
        return StatsResponse(
            text_collection=app_settings.text_collection,
            text_count=svc.vector_store.count(app_settings.text_collection),
            visual_collection=app_settings.visual_collection,
            visual_count=svc.vector_store.count(app_settings.visual_collection),
            chroma_path=str(app_settings.resolve_path(app_settings.chroma_path)),
            storage_root=str(app_settings.resolve_path(app_settings.storage_root)),
            manifest=str(app_settings.resolve_path(app_settings.manifest_path)),
            device=app_settings.device,
            embedding=app_settings.embedding_model,
            llm_model=app_settings.llm_model,
        )

    @v1.post("/search", response_model=SearchResponse)
    async def search(body: SearchRequest, request: Request) -> SearchResponse:
        svc: AppServices = request.app.state.services
        app_settings: Settings = request.app.state.settings
        lock: asyncio.Lock = request.app.state.inference_lock
        async with lock:
            try:
                hits = await asyncio.to_thread(
                    svc.retriever.search,
                    body.query,
                    body.k,
                    not body.text_only,
                    source=body.source,
                    course=body.course,
                    content_type=body.content_type,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
                ) from exc
        citations, assets = hits_to_citations_and_assets(hits, settings=app_settings)
        return SearchResponse(hits=citations, assets=assets)

    @v1.post("/ask")
    async def ask(body: AskRequest, request: Request):
        if body.stream:
            return EventSourceResponse(
                _ask_sse(request, body),
                ping=15000,
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        return await _ask_json(request, body)

    app.include_router(v1)
    return app


async def _ask_json(request: Request, body: AskRequest) -> AskResponse:
    svc: AppServices = request.app.state.services
    app_settings: Settings = request.app.state.settings
    lock: asyncio.Lock = request.app.state.inference_lock
    async with lock:
        try:
            answer = await asyncio.to_thread(
                svc.generator.generate_answer,
                body.query,
                k=body.k,
                include_visual=not body.text_only,
                enhance=body.enhance,
                source=body.source,
                course=body.course,
                content_type=body.content_type,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
    citations, assets = hits_to_citations_and_assets(
        svc.generator.last_hits, settings=app_settings
    )
    return AskResponse(
        answer=answer,
        citations=citations,
        assets=assets,
        query=_query_plan(svc.generator.last_enhanced),
    )


async def _ask_sse(request: Request, body: AskRequest) -> AsyncIterator[Any]:
    svc: AppServices = request.app.state.services
    app_settings: Settings = request.app.state.settings
    lock: asyncio.Lock = request.app.state.inference_lock
    request_id = str(uuid.uuid4())
    generator = svc.generator

    def take(it: Iterator[AskEvent]) -> AskEvent | object:
        return next(it, _SENTINEL)

    async with lock:
        try:
            iterator = generator.iter_ask_events(
                body.query,
                k=body.k,
                include_visual=not body.text_only,
                enhance=body.enhance,
                source=body.source,
                course=body.course,
                content_type=body.content_type,
            )
            while True:
                if await request.is_disconnected():
                    break
                item = await asyncio.to_thread(take, iterator)
                if item is _SENTINEL:
                    break
                event = item
                assert isinstance(event, AskEvent)  
                if event.name == "sources":
                    citations, assets = hits_to_citations_and_assets(
                        generator.last_hits, settings=app_settings
                    )
                    yield sse_event(
                        "sources",
                        {
                            "citations": [dump_model(c) for c in citations],
                            "assets": [dump_model(a) for a in assets],
                        },
                    )
                elif event.name == "done":
                    yield sse_event("done", {"request_id": request_id})
                else:
                    yield sse_event(event.name, event.data)
        except ValueError as exc:
            yield sse_event("error", {"message": str(exc)})
        except Exception:
            logger.exception("ask stream failed")
            yield sse_event("error", {"message": "Generation failed"})


def _query_plan(enhanced: EnhancedQuery | None) -> QueryPlan | None:
    if enhanced is None:
        return None
    return QueryPlan(
        rewritten=enhanced.rewritten,
        subqueries=list(enhanced.subqueries),
        step_back=enhanced.step_back or "",
    )


def _cors_origins(value: str) -> list[str]:
    parts = [item.strip() for item in (value or "*").split(",") if item.strip()]
    return parts or ["*"]


app = create_app()
