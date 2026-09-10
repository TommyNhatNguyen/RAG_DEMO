from __future__ import annotations

from typing import Any

from app.eval.metrics import HANDOFF_MAPPING, METRIC_KEYS, mean, weakest_metric

FAITHFULNESS_WARN = 0.85


def build_report(
    traces: list[dict[str, Any]],
    *,
    llm_means: dict[str, float | None] | None = None,
) -> dict[str, Any]:
    path_recalls = [float(t["path_recall"]) for t in traces if t.get("path_recall") is not None]
    path_precs = [float(t["path_precision"]) for t in traces if t.get("path_precision") is not None]
    by_kind: dict[str, dict[str, list[float]]] = {}
    for trace in traces:
        kind = str(trace.get("kind") or "theory")
        bucket = by_kind.setdefault(
            kind, {"path_recall": [], "path_precision": [], "path_recall_at_1": [], "path_recall_at_5": [], "path_recall_at_10": []}
        )
        if trace.get("path_recall") is not None:
            bucket["path_recall"].append(float(trace["path_recall"]))
        if trace.get("path_precision") is not None:
            bucket["path_precision"].append(float(trace["path_precision"]))
        for key in ("path_recall_at_1", "path_recall_at_5", "path_recall_at_10"):
            if trace.get(key) is not None:
                bucket[key].append(float(trace[key]))

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

    kind_summary = {
        kind: {
            "n": len(traces_for_kind(traces, kind)),
            "path_recall": mean(vals["path_recall"]),
            "path_precision": mean(vals["path_precision"]),
            "path_recall_at_1": mean(vals.get("path_recall_at_1") or []),
            "path_recall_at_5": mean(vals.get("path_recall_at_5") or []),
            "path_recall_at_10": mean(vals.get("path_recall_at_10") or []),
        }
        for kind, vals in by_kind.items()
    }

    return {
        "n": len(traces),
        "scores": scores,
        "by_kind": kind_summary,
        "weakest_metric": weakest,
        "next_step": HANDOFF_MAPPING.get(weakest or "", None),
        "warnings": warnings,
        "items": traces,
    }


def traces_for_kind(traces: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [t for t in traces if str(t.get("kind") or "theory") == kind]


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
