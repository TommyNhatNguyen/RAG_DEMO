from __future__ import annotations

from typing import Any


def format_retrieval_report(report: dict[str, Any]) -> str:
    lines = [
        f"retrieval-benchmark system={report.get('system_id')} "
        f"n_questions={report.get('counts', {}).get('questions', 0)}",
    ]
    macro = report.get("macro_average_answerable") or {}
    lines.append(f"  scored={report.get('counts', {}).get('answerable_scored', 0)}")
    for key, value in macro.items():
        if value is not None:
            lines.append(f"    {key}={float(value):.4f}")

    coverage = report.get("corpus_coverage") or {}
    rate = coverage.get("rate")
    lines.append(
        "  corpus_coverage="
        + (f"{float(rate):.4f}" if rate is not None else "n/a")
        + f" (indexed={coverage.get('answerable_with_indexed_ground_truth', 0)}, "
        f"missing={coverage.get('answerable_missing_indexed_ground_truth', 0)})"
    )
    aliases = report.get("resource_id_aliases_applied")
    if aliases:
        lines.append(f"  resource_id_aliases_applied={aliases}")

    for group_name in ("by_category", "by_difficulty"):
        buckets = report.get(group_name) or {}
        if not buckets:
            continue
        lines.append(f"  {group_name}:")
        for label, entry in buckets.items():
            f1_10 = entry.get("f1@10")
            f1_s = f"{float(f1_10):.4f}" if f1_10 is not None else "n/a"
            lines.append(f"    {label:20s} n={entry.get('n', 0):4d} f1@10={f1_s}")

    for group_name in ("excluded_by_category", "excluded_by_difficulty"):
        counts = report.get(group_name) or {}
        if counts:
            lines.append(f"  {group_name}: " + ", ".join(f"{k}={v}" for k, v in counts.items()))

    return "\n".join(lines)
