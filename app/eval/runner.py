from __future__ import annotations

import logging
from typing import Any

from app.eval.golden import GoldenItem
from app.eval.judge import score_reference_free, score_with_judge
from app.eval.metrics import path_precision_at_k, path_recall_at_k
from app.eval.ragas_backend import score_with_ragas
from app.eval.report import build_report
from app.eval.retrieval_benchmark import metrics_at_k, serialize_hit
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
    resource_id_aliases: dict[str, str] | None = None,
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
                resource_id_aliases=resource_id_aliases,
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
    resource_id_aliases: dict[str, str] | None = None,
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
    trace = {
        "id": item.id,
        "kind": item.kind,
        "difficulty": item.extra.get("difficulty") if isinstance(item.extra, dict) else None,
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

    evidence = item.extra.get("evidence") if isinstance(item.extra, dict) else None
    if evidence and hits:
        serialized = [
            serialize_hit(item.id, rank, hit) for rank, hit in enumerate(hits, start=1)
        ]
        citation = metrics_at_k(evidence, serialized, len(serialized), resource_id_aliases)
        trace["citation_precision"] = citation["precision"]
        trace["citation_recall"] = citation["recall"]
        trace["citation_f1"] = citation["f1"]
    return trace


def _llm_scores(
    services: Any,
    traces: list[dict[str, Any]],
    *,
    use_ragas: bool,
) -> dict[str, float | None]:
    chat = getattr(services.generator, "_chat", None)
    # A bridged questions_draft*.json set (see question_draft_bridge.py) has
    # no gold reference answer at all — context_precision/context_recall and
    # RAGAs' reference-dependent metrics would just score against "", which
    # is misleading rather than merely imprecise. Detect and branch instead.
    reference_free = bool(traces) and all(
        not str(trace.get("ground_truth") or "").strip() for trace in traces
    )
    if use_ragas and not reference_free:
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
    if reference_free:
        bucket: dict[str, list[float]] = {key: [] for key in ("faithfulness", "answer_relevancy")}
        for trace in traces:
            try:
                scored = score_reference_free(
                    chat,
                    question=str(trace.get("question") or ""),
                    contexts=list(trace.get("contexts") or []),
                    answer=str(trace.get("answer") or ""),
                )
            except Exception:
                logger.exception("Reference-free judge failed for %s", trace.get("id"))
                continue
            for key, values in bucket.items():
                if key in scored:
                    values.append(scored[key])
        return {
            key: (sum(vals) / len(vals) if vals else None) for key, vals in bucket.items()
        }
    bucket = {key: [] for key in ("faithfulness", "answer_relevancy", "context_precision", "context_recall")}
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
