from __future__ import annotations

from typing import Any

from app.eval.metrics import HANDOFF_MAPPING, METRIC_KEYS, mean, weakest_metric

FAITHFULNESS_WARN = 0.85


_BUCKET_METRIC_KEYS = (
    "path_recall",
    "path_precision",
    "path_recall_at_1",
    "path_recall_at_5",
    "path_recall_at_10",
)


def _bucket_summary(
    traces: list[dict[str, Any]], group_key: str, *, default: str = "unknown"
) -> dict[str, dict[str, Any]]:
    counts: dict[str, int] = {}
    buckets: dict[str, dict[str, list[float]]] = {}
    for trace in traces:
        label = str(trace.get(group_key) or default)
        counts[label] = counts.get(label, 0) + 1
        bucket = buckets.setdefault(label, {key: [] for key in _BUCKET_METRIC_KEYS})
        for key in _BUCKET_METRIC_KEYS:
            if trace.get(key) is not None:
                bucket[key].append(float(trace[key]))
    return {
        label: {"n": counts[label], **{key: mean(vals) for key, vals in vals_by_key.items()}}
        for label, vals_by_key in buckets.items()
    }


def build_report(
    traces: list[dict[str, Any]],
    *,
    llm_means: dict[str, float | None] | None = None,
) -> dict[str, Any]:
    path_recalls = [float(t["path_recall"]) for t in traces if t.get("path_recall") is not None]
    path_precs = [float(t["path_precision"]) for t in traces if t.get("path_precision") is not None]

    llm_means = llm_means or {}
    scores: dict[str, float | None] = {
        "path_recall": mean(path_recalls),
        "path_precision": mean(path_precs),
        "path_recall_at_1": mean(
            [float(t["path_recall_at_1"]) for t in traces if t.get("path_recall_at_1") is not None]
        ),
        "path_recall_at_5": mean(
            [float(t["path_recall_at_5"]) for t in traces if t.get("path_recall_at_5") is not None]
        ),
        "path_recall_at_10": mean(
            [float(t["path_recall_at_10"]) for t in traces if t.get("path_recall_at_10") is not None]
        ),
    }
    for key in METRIC_KEYS:
        scores[key] = llm_means.get(key)

    weakest = weakest_metric(scores)
    warnings: list[str] = []
    faith = scores.get("faithfulness")
    if faith is not None and faith < FAITHFULNESS_WARN:
        warnings.append(
            f"faithfulness={faith:.3f} < {FAITHFULNESS_WARN} (warning only; not a CI fail)"
        )

    return {
        "n": len(traces),
        "scores": scores,
        "by_kind": _bucket_summary(traces, "kind", default="theory"),
        "by_difficulty": _bucket_summary(traces, "difficulty"),
        "weakest_metric": weakest,
        "next_step": HANDOFF_MAPPING.get(weakest or "", None),
        "warnings": warnings,
        "items": traces,
    }


def format_report(report: dict[str, Any]) -> str:
    scores = report.get("scores") or {}
    lines = [f"eval n={report.get('n', 0)}"]
    for key in (
        "path_recall",
        "path_precision",
        "path_recall_at_1",
        "path_recall_at_5",
        "path_recall_at_10",
        *METRIC_KEYS,
    ):
        value = scores.get(key)
        if value is None:
            continue
        lines.append(f"  {key}={float(value):.3f}")
    weakest = report.get("weakest_metric")
    if weakest:
        lines.append(f"weakest_metric={weakest}")
        nxt = report.get("next_step")
        if nxt:
            lines.append(f"next_step={nxt}")
    for warning in report.get("warnings") or []:
        lines.append(f"WARNING: {warning}")
    return "\n".join(lines)
