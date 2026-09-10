from __future__ import annotations

from app.models.retrieval import RetrievalResult

RRF_K = 60


def merge_results(*groups: list[RetrievalResult]) -> list[RetrievalResult]:
    by_id: dict[str, RetrievalResult] = {}
    for group in groups:
        for item in group:
            existing = by_id.get(item.id)
            if existing is None or item.score > existing.score:
                by_id[item.id] = item
    return list(by_id.values())


def rrf_merge(
    groups: list[list[RetrievalResult]],
    *,
    k: int = RRF_K,
) -> list[RetrievalResult]:
    """Fuse ranked lists with reciprocal rank fusion. Score becomes RRF; payload keeps the highest original score item."""
    if not groups:
        return []
    nonempty = [group for group in groups if group]
    if len(nonempty) == 1:
        return list(nonempty[0])
    rrf_scores: dict[str, float] = {}
    items: dict[str, RetrievalResult] = {}
    for group in nonempty:
        for rank, item in enumerate(group, start=1):
            rrf_scores[item.id] = rrf_scores.get(item.id, 0.0) + 1.0 / (k + rank)
            items[item.id] = _prefer_payload(items.get(item.id), item)
    fused = [
        item.model_copy(update={"score": rrf_scores[item.id]})
        for item in items.values()
    ]
    fused.sort(key=lambda item: item.score, reverse=True)
    return fused


def _cosine(item: RetrievalResult) -> float | None:
    value = (item.metadata or {}).get("cosine")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _prefer_payload(
    existing: RetrievalResult | None, incoming: RetrievalResult
) -> RetrievalResult:
    if existing is None:
        return incoming
    existing_cos = _cosine(existing)
    incoming_cos = _cosine(incoming)
    if incoming_cos is not None and (
        existing_cos is None or incoming_cos > existing_cos
    ):
        chosen, other = incoming, existing
    elif existing_cos is not None:
        chosen, other = existing, incoming
    else:
        chosen, other = (incoming, existing) if incoming.score > existing.score else (existing, incoming)
    meta = dict(chosen.metadata or {})
    other_cos = _cosine(other)
    chosen_cos = _cosine(chosen)
    if other_cos is not None and (chosen_cos is None or other_cos > chosen_cos):
        meta["cosine"] = other_cos
        chosen = chosen.model_copy(update={"metadata": meta})
    return chosen
