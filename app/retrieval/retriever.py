from __future__ import annotations

import logging
import re
import unicodedata
from typing import TYPE_CHECKING, Any

from app.config.settings import Settings
from app.embeddings.base import TextEmbedder, VLEmbedder
from app.models.retrieval import RetrievalResult
from app.retrieval.compress import compress_hits
from app.retrieval.diversity import diversify_by_file
from app.retrieval.expand import expand_hits
from app.retrieval.filters import chroma_where, folder_prefix, matches_course, matches_prefix
from app.retrieval.merger import rrf_merge
from app.retrieval.reranker import ScoreReranker
from app.retrieval.sparse import BM25Index
from app.vectorstore.chroma import ChromaVectorStore

if TYPE_CHECKING:
    from app.generation.query_enhance import EnhancedQuery

logger = logging.getLogger(__name__)


def process_user_query(raw_query: str) -> str:
    if raw_query is None:
        return ""
    text = unicodedata.normalize("NFC", str(raw_query))
    text = re.sub(r"\s+", " ", text).strip()
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch == "\n")
    return text.strip()


def source_where(source: str | None) -> dict[str, Any] | None:
    return chroma_where(source)


class MultimodalRetriever:
    def __init__(
        self,
        settings: Settings,
        vector_store: ChromaVectorStore,
        text_embedder: TextEmbedder,
        vl_embedder: VLEmbedder | None = None,
        reranker: ScoreReranker | None = None,
        bm25: BM25Index | None = None,
    ) -> None:
        self.settings = settings
        self.vector_store = vector_store
        self.text_embedder = text_embedder
        self.vl_embedder = vl_embedder
        self.reranker = reranker or ScoreReranker()
        self._bm25 = bm25
        self._bm25_loaded = bm25 is not None

    def search(
        self,
        raw_query: str,
        k: int | None = None,
        include_visual: bool = True,
        *,
        enhanced: EnhancedQuery | None = None,
        source: str | None = None,
        course: str | None = None,
        content_type: str | None = None,
    ) -> list[RetrievalResult]:
        query = process_user_query(raw_query)
        if not query:
            raise ValueError("Empty query after processing.")
        k = k or self.settings.retriever_k
        fetch_k = max(k, self.settings.retriever_fetch_k)
        prefix = folder_prefix(source)
        # Normal app mode keeps compatibility with legacy vectors that may lack
        # `course`. Controlled benchmarks can enable a strict Chroma pre-filter.
        where = chroma_where(
            source,
            course=course if self.settings.course_prefilter else None,
            content_type=content_type,
        )
        dense_n = fetch_k * 5 if prefix or course else fetch_k

        text_queries = [query]
        visual_query = query
        from app.generation.catalog import catalog_subqueries, is_catalog_query

        if enhanced is not None:
            text_queries = enhanced.text_search_queries() or [query]
            visual_query = process_user_query(enhanced.rewritten or query) or query
        elif is_catalog_query(query):
            extras = catalog_subqueries(query)
            text_queries = [query]
            for extra in extras:
                cleaned = process_user_query(extra)
                if cleaned and cleaned.casefold() not in {query.casefold()}:
                    text_queries.append(cleaned)

        logger.info(
            "Searching queries=%s visual=%s fetch_k=%s k=%s where=%s prefix=%s course=%s",
            len(text_queries),
            visual_query[:80],
            fetch_k,
            k,
            where,
            prefix,
            course,
        )

        text_groups: list[list[RetrievalResult]] = []
        for text_query in text_queries:
            text_groups.append(
                self._post_filter(
                    self._search_collection(
                        collection=self.settings.text_collection,
                        embedding=self.text_embedder.embed_query(text_query),
                        k=dense_n,
                        where=where,
                    ),
                    prefix=prefix,
                    course=course,
                    content_type=content_type,
                    limit=fetch_k,
                )
            )

        sparse_group = self._sparse_group(
            text_queries[0],
            fetch_k=fetch_k,
            prefix=prefix,
            course=course,
            content_type=content_type,
        )
        if sparse_group:
            text_groups.append(sparse_group)

        if enhanced is not None and self.settings.query_hyde:
            hyde = process_user_query(enhanced.hyde or "")
            if hyde:
                text_groups.append(
                    self._post_filter(
                        self._search_collection(
                            collection=self.settings.text_collection,
                            embedding=self.text_embedder.embed_query(hyde),
                            k=dense_n,
                            where=where,
                        ),
                        prefix=prefix,
                        course=course,
                        content_type=content_type,
                        limit=fetch_k,
                    )
                )

        visual_hits: list[RetrievalResult] = []
        if include_visual and self.vl_embedder is not None:
            try:
                visual_hits = self._post_filter(
                    self._search_collection(
                        collection=self.settings.visual_collection,
                        embedding=self.vl_embedder.embed_query(visual_query),
                        k=dense_n,
                        where=where,
                    ),
                    prefix=prefix,
                    course=course,
                    content_type=content_type,
                    limit=fetch_k,
                )
            except Exception:
                logger.exception("Visual search failed; returning text hits only")

        groups = list(text_groups)
        if visual_hits:
            groups.append(visual_hits)
        if len(groups) > 1:
            fused = rrf_merge(groups)
        else:
            fused = groups[0] if groups else []

        ranked = self.reranker.rerank(visual_query, fused, source=source)
        diversified = diversify_by_file(
            ranked,
            k=k,
            max_per_file=self.settings.retrieve_max_per_file,
        )
        expanded = diversified
        if self.settings.context_expand:
            expanded = expand_hits(
                diversified, self.vector_store, self.settings.text_collection
            )
        compressed = expanded
        if self.settings.context_compress:
            extra = list(text_queries)
            if enhanced is not None:
                extra = enhanced.text_search_queries() or extra
            compressed = compress_hits(expanded, query, extra)
        return compressed[:k]

    def _sparse_group(
        self,
        query: str,
        *,
        fetch_k: int,
        prefix: str | None,
        course: str | None,
        content_type: str | None,
    ) -> list[RetrievalResult]:
        index = self._bm25_index()
        if index is None:
            return []
        sparse_k = max(fetch_k * 10, 80) if prefix or course else fetch_k
        return self._post_filter(
            index.search(query, sparse_k),
            prefix=prefix,
            course=course,
            content_type=content_type,
            limit=fetch_k,
        )

    def _bm25_index(self) -> BM25Index | None:
        if not self.settings.hybrid_search:
            return None
        if self._bm25_loaded:
            return self._bm25
        self._bm25_loaded = True
        path = self.settings.resolve_path(self.settings.bm25_path)
        loaded = BM25Index.load(path)
        if loaded is None:
            logger.warning("BM25 index missing at %s; using dense retrieval only", path)
        self._bm25 = loaded
        return self._bm25

    def _post_filter(
        self,
        results: list[RetrievalResult],
        *,
        prefix: str | None,
        course: str | None,
        content_type: str | None,
        limit: int,
    ) -> list[RetrievalResult]:
        out: list[RetrievalResult] = []
        for item in results:
            meta = item.metadata or {}
            rel = str(meta.get("relative_path") or "")
            if prefix and not matches_prefix(rel, prefix):
                continue
            if course and not matches_course(rel, course, meta.get("course")):
                continue
            if content_type and str(meta.get("content_type") or "") != content_type:
                continue
            out.append(item)
            if len(out) >= limit:
                break
        return out

    def _search_collection(
        self,
        collection: str,
        embedding: list[float],
        k: int,
        where: dict[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        raw = self.vector_store.search(collection, embedding, k, where=where)
        results: list[RetrievalResult] = []
        for hit in raw:
            meta = dict(hit.get("metadata") or {})
            cosine = float(hit["score"])
            meta["cosine"] = cosine
            results.append(
                RetrievalResult(
                    id=hit["id"],
                    score=cosine,
                    content_type=str(meta.get("content_type") or "text"),
                    content=hit.get("document"),
                    metadata=meta,
                )
            )
        return results
