#!/usr/bin/env python3
"""Tính lại số liệu truy xuất cho thực nghiệm bổ sung trên bộ câu hỏi v7
(`questions_draft_v7.json`, 400 câu, không có bản ghi trùng nội dung).

Khác với `retrieval_stats.py` (bộ câu hỏi cũ, có 37 nhóm trùng nên phải bootstrap
theo cụm truy vấn), bộ v7 có 400/400 câu hỏi và 400/400 cặp (môn, câu hỏi) khác
nhau — mỗi bản ghi là một quan sát độc lập, nên chỉ cần bootstrap theo bản ghi.

Đọc trực tiếp từ working tree (các tệp này chưa được commit tại thời điểm viết).

Chạy từ gốc repo:
    python3 document/KLTN_MM-RAG/tools/retrieval_stats_v7.py
    python3 document/KLTN_MM-RAG/tools/retrieval_stats_v7.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import random
import statistics as st
from collections import Counter
from pathlib import Path

SEED = 20260930  # ngày chạy benchmark hybrid+rerank đã sửa (2026-09-30)
RESAMPLES = 10_000
KS = ("1", "5", "10")
METRICS = ("precision", "recall", "f1")

SYSTEMS = {
    "baseline": "v7_baseline_retrieval_metrics.json",
    "hybrid_norerank": "v7_proposed_hybrid_norerank_metrics.json",
    "hybrid_rerank_buggy": "v7_proposed_hybrid_rerank_metrics.json",
    "hybrid_rerank_fixed": "v7_proposed_hybrid_rerank_fixed_metrics.json",
}


def load_json(key: str, directory: Path) -> dict:
    return json.loads((directory / SYSTEMS[key]).read_text(encoding="utf-8"))


def ci95(samples: list[float]) -> tuple[float, float]:
    samples = sorted(samples)
    return samples[int(0.025 * len(samples)) - 1], samples[int(0.975 * len(samples)) - 1]


def macro_table(reports: dict[str, dict]) -> dict[str, dict[str, float]]:
    return {key: r["macro_average_answerable"] for key, r in reports.items()}


def by_group_table(reports: dict[str, dict], group: str) -> dict[str, dict[str, dict]]:
    return {key: r[group] for key, r in reports.items()}


def bootstrap_pair(pa: dict, pb: dict, ids: list[str], seed: int) -> dict[str, dict]:
    """Hiệu số pb - pa, bootstrap ghép cặp theo bản ghi (hợp lệ vì không có trùng)."""
    rng = random.Random(seed)
    out: dict[str, dict] = {}

    def diff(metric: str, k: str, records: list[str]) -> float:
        return st.mean(pb[i][k][metric] - pa[i][k][metric] for i in records)

    for k in KS:
        for metric in METRICS:
            obs = diff(metric, k, ids)
            samples = [diff(metric, k, [rng.choice(ids) for _ in ids]) for _ in range(RESAMPLES)]
            lo, hi = ci95(samples)
            out[f"{metric}@{k}"] = {"diff": obs, "ci95": [lo, hi], "ci_excludes_zero": bool(lo > 0 or hi < 0)}
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="evals/results", help="thư mục chứa các tệp kết quả v7")
    parser.add_argument("--json", default=None, help="ghi kết quả ra file JSON")
    args = parser.parse_args()
    directory = Path(args.dir)

    reports = {key: load_json(key, directory) for key in SYSTEMS}
    per_q = {
        key: {r["question_id"]: r["metrics"] for r in rep["per_question"]}
        for key, rep in reports.items()
    }
    cat = {key: {r["question_id"]: r["category"] for r in rep["per_question"]} for key, rep in reports.items()}
    diff_lvl = {key: {r["question_id"]: r["difficulty"] for r in rep["per_question"]} for key, rep in reports.items()}

    ids_per_system = {key: sorted(p) for key, p in per_q.items()}
    for key, ids in ids_per_system.items():
        assert len(ids) == reports[key]["counts"]["answerable_scored"], key
    ids = ids_per_system["baseline"]
    assert all(ids_per_system[key] == ids for key in SYSTEMS), "các hệ thống phải được chấm trên cùng tập câu hỏi"

    out: dict = {
        "n_questions_scored": {key: reports[key]["counts"]["answerable_scored"] for key in SYSTEMS},
        "n_questions_total": {key: reports[key]["counts"]["questions"] for key in SYSTEMS},
        "corpus_coverage_rate": {key: reports[key]["corpus_coverage"]["rate"] for key in SYSTEMS},
        "resource_id_aliases_applied": {key: reports[key].get("resource_id_aliases_applied") for key in SYSTEMS},
        "macro": macro_table(reports),
        "by_category": by_group_table(reports, "by_category"),
        "by_difficulty": by_group_table(reports, "by_difficulty"),
    }

    out["hit_rate"] = {
        key: {k: sum(m[i][k]["relevant_results"] > 0 for i in ids) / len(ids) for k in KS}
        for key, m in per_q.items()
    }

    evidence = [per_q["baseline"][i]["1"]["total_ground_truth"] for i in ids]
    out["evidence_per_question"] = {
        "distribution": dict(sorted(Counter(evidence).items())),
        "mean": st.mean(evidence),
    }

    # Hiệu số có ý nghĩa cho câu chuyện chính: baseline so với từng biến thể hybrid.
    out["bootstrap"] = {
        "seed": SEED,
        "resamples": RESAMPLES,
        "note": "Bootstrap theo bản ghi (record-level); hợp lệ vì v7 không có câu hỏi trùng nội dung.",
        "baseline_vs_hybrid_norerank": bootstrap_pair(per_q["baseline"], per_q["hybrid_norerank"], ids, SEED),
        "baseline_vs_hybrid_rerank_fixed": bootstrap_pair(per_q["baseline"], per_q["hybrid_rerank_fixed"], ids, SEED),
        "hybrid_norerank_vs_hybrid_rerank_fixed": bootstrap_pair(per_q["hybrid_norerank"], per_q["hybrid_rerank_fixed"], ids, SEED),
    }

    print(f"Câu hỏi được chấm (mỗi hệ thống): {out['n_questions_scored']}")
    print(f"Độ phủ kho học liệu: {out['corpus_coverage_rate']}")
    print("\nMacro P/R/F1@K:")
    for key in SYSTEMS:
        m = out["macro"][key]
        print(f"  {key:24s}: " + " ".join(f"{k}={m[k]:.4f}" for k in m))
    print("\nTỷ lệ trúng:", json.dumps(out["hit_rate"], ensure_ascii=False))
    print("\nBootstrap (seed={}, {} lần), theo bản ghi:".format(SEED, RESAMPLES))
    for pair_name in ("baseline_vs_hybrid_norerank", "baseline_vs_hybrid_rerank_fixed", "hybrid_norerank_vs_hybrid_rerank_fixed"):
        print(f"  --- {pair_name} ---")
        for m, v in out["bootstrap"][pair_name].items():
            flag = "KHÔNG chứa 0" if v["ci_excludes_zero"] else "chứa 0"
            print(f"    {m:>11}: {v['diff']:+.4f} [{v['ci95'][0]:+.4f}; {v['ci95'][1]:+.4f}]  {flag}")

    print("\nPhân rã theo category (f1@10):")
    for key in SYSTEMS:
        row = out["by_category"][key]
        print(f"  {key:24s}: " + " ".join(f"{c}={row[c]['f1@10']:.4f}" for c in row))

    if args.json:
        Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nĐã ghi {args.json}")


if __name__ == "__main__":
    main()
