from __future__ import annotations

import logging
from typing import Any

from app.eval.golden import GoldenItem
from app.eval.judge import score_with_judge
from app.eval.metrics import path_precision_at_k, path_recall_at_k
from app.eval.ragas_backend import score_with_ragas
from app.eval.report import build_report
from app.generation.context import relative_path_for_hit
from app.models.retrieval import RetrievalResult

logger = logging.getLogger(__name__)


def run_eval(
    services: Any,
    items: list[GoldenItem],
    *,
    text_only: bool = True,
    retrieve_only: bool = False,
    enhance: bool = False,
    k: int | None = None,
    use_ragas: bool = True,
) -> dict[str, Any]:
    traces: list[dict[str, Any]] = []
    for item in items:
        traces.append(
            _run_one(
                services,
                item,
                text_only=text_only,
                retrieve_only=retrieve_only,
                enhance=enhance,
                k=k,
            )
        )
    llm_means: dict[str, float | None] = {}
    if not retrieve_only:
        llm_means = _llm_scores(services, traces, use_ragas=use_ragas)
    return build_report(traces, llm_means=llm_means)


def _run_one(
    services: Any,
    item: GoldenItem,
    *,
    text_only: bool,
    retrieve_only: bool,
    enhance: bool,
    k: int | None,
) -> dict[str, Any]:
    include_visual = not text_only
    hits: list[RetrievalResult]
    answer = ""
    if retrieve_only:
        hits = services.retriever.search(
            item.question,
            k=k,
            include_visual=include_visual,
            source=item.source,
            course=item.course,
            content_type=item.content_type,
        )
    else:
        answer = services.generator.generate_answer(
            item.question,
            k=k,
            include_visual=include_visual,
            enhance=enhance,
            source=item.source,
            course=item.course,
            content_type=item.content_type,
        )
        hits = list(services.generator.last_hits or [])
    contexts = [(hit.content or "").strip() for hit in hits]
    paths = [relative_path_for_hit(hit) for hit in hits]
    recall = path_recall_at_k(item.expected_paths, hits)
    precision = path_precision_at_k(item.expected_paths, hits)
    return {
        "id": item.id,
        "kind": item.kind,
        "question": item.question,
        "ground_truth": item.ground_truth,
        "answer": answer,
        "contexts": contexts,
        "paths": paths,
        "cosines": [
            (hit.metadata or {}).get("cosine") for hit in hits
        ],
        "path_recall": recall,
        "path_precision": precision,
        "path_recall_at_1": path_recall_at_k(item.expected_paths, hits, 1),
        "path_recall_at_5": path_recall_at_k(item.expected_paths, hits, 5),
        "path_recall_at_10": path_recall_at_k(item.expected_paths, hits, 10),
        "expected_paths": list(item.expected_paths),
    }


def _llm_scores(
    services: Any,
    traces: list[dict[str, Any]],
    *,
    use_ragas: bool,
) -> dict[str, float | None]:
    chat = getattr(services.generator, "_chat", None)
    if use_ragas:
        ragas_scores = score_with_ragas(
            traces,
            llm=chat if chat is not None else None,
            embeddings=getattr(services, "text_embedder", None),
        )
        if ragas_scores:
            return ragas_scores
    if chat is None:
        logger.warning("No LLM judge available; skipping faithfulness/relevancy/precision/recall")
        return {}
    bucket: dict[str, list[float]] = {key: [] for key in ("faithfulness", "answer_relevancy", "context_precision", "context_recall")}
    for trace in traces:
        try:
            scored = score_with_judge(
                chat,
                question=str(trace.get("question") or ""),
                reference=str(trace.get("ground_truth") or ""),
                contexts=list(trace.get("contexts") or []),
                answer=str(trace.get("answer") or ""),
            )
        except Exception:
            logger.exception("Local judge failed for %s", trace.get("id"))
            continue
        for key, values in bucket.items():
            if key in scored:
                values.append(scored[key])
        if "completeness" in scored:
            trace["completeness"] = scored["completeness"]
    return {
        key: (sum(vals) / len(vals) if vals else None) for key, vals in bucket.items()
    }
