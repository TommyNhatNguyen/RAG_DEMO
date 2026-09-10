from __future__ import annotations

from collections import defaultdict

from app.generation.context import relative_path_for_hit
from app.models.retrieval import RetrievalResult


def diversify_by_file(
    results: list[RetrievalResult],
    *,
    k: int,
    max_per_file: int = 2,
) -> list[RetrievalResult]:
    if k <= 0 or not results:
        return []
    cap = max(1, max_per_file)
    buckets: dict[str, list[RetrievalResult]] = defaultdict(list)
    order: list[str] = []
    for item in results:
        key = relative_path_for_hit(item)
        if key not in buckets:
            order.append(key)
        if len(buckets[key]) < cap:
            buckets[key].append(item)
    out: list[RetrievalResult] = []
    index = 0
    while len(out) < k:
        progressed = False
        for key in order:
            bucket = buckets[key]
            if index < len(bucket):
                out.append(bucket[index])
                progressed = True
                if len(out) >= k:
                    break
        if not progressed:
            break
        index += 1
    return out
