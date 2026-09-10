from __future__ import annotations

from app.generation.context import relative_path_for_hit
from app.ids import nfc
from app.models.retrieval import RetrievalResult

METRIC_KEYS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
)

HANDOFF_MAPPING = {
    "context_precision": "chunking / metadata filters",
    "path_precision": "chunking / metadata filters",
    "faithfulness": "prompt / extractive compress",
    "context_recall": "hybrid / fetch_k / optional HyDE",
    "path_recall": "hybrid / fetch_k / optional HyDE",
    "answer_relevancy": "query enhance / generation prompt",
}


def path_recall_at_k(expected_paths: list[str], hits: list[RetrievalResult], k: int | None = None) -> float:
    expected = _norm_paths(expected_paths)
    if not expected:
        return 1.0
    sliced = hits if k is None else hits[: max(0, k)]
    got = _hit_paths(sliced)
    return len(expected & got) / len(expected)


def path_precision_at_k(expected_paths: list[str], hits: list[RetrievalResult], k: int | None = None) -> float:
    expected = _norm_paths(expected_paths)
    sliced = hits if k is None else hits[: max(0, k)]
    got = _hit_paths(sliced)
    if not got:
        return 1.0 if not expected else 0.0
    if not expected:
        return 1.0
    return len(expected & got) / len(got)


def mean(values: list[float]) -> float | None:
    numbers = [float(v) for v in values if v is not None]
    if not numbers:
        return None
    return sum(numbers) / len(numbers)


def weakest_metric(scores: dict[str, float | None]) -> str | None:
    ranked: list[tuple[str, float]] = []
    for key in METRIC_KEYS:
        value = scores.get(key)
        if value is None:
            continue
        ranked.append((key, float(value)))
    if not ranked:
        for key in ("path_recall", "path_precision"):
            value = scores.get(key)
            if value is None:
                continue
            ranked.append((key, float(value)))
    if not ranked:
        return None
    ranked.sort(key=lambda row: row[1])
    return ranked[0][0]


def _norm_paths(paths: list[str]) -> set[str]:
    return {nfc(path.replace("\\", "/").lstrip("./")) for path in paths if path}


def _hit_paths(hits: list[RetrievalResult]) -> set[str]:
    out: set[str] = set()
    for hit in hits:
        rel = relative_path_for_hit(hit)
        if rel and rel != "unknown":
            out.add(nfc(rel.replace("\\", "/").lstrip("./")))
    return out
