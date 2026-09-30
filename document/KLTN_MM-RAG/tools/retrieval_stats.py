#!/usr/bin/env python3
"""Tính lại các số liệu Chương 4 từ file kết quả gốc (chỉ dùng thư viện chuẩn).

Mặc định đọc `evals/results/{baseline,proposed}_retrieval_{metrics.json,results.jsonl}` từ git HEAD
của repo (các file này đã bị xóa khỏi working tree nhưng còn trong HEAD).
Có thể chỉ định thư mục bằng --dir.

Chạy từ gốc repo:
    python3 document/KLTN_MM-RAG/tools/retrieval_stats.py
    python3 document/KLTN_MM-RAG/tools/retrieval_stats.py --json out.json

Nội dung:
  1. Macro P/R/F1@K, tỷ lệ trúng, phân bố số bằng chứng.
  2. Mức độ lặp lại của câu hỏi: nhiều bản ghi có cùng (môn, nội dung câu hỏi) nên truy xuất cho kết quả
     giống hệt nhau; do đó các bản ghi KHÔNG độc lập.
  3. Bootstrap ghép cặp hiệu số proposed - baseline theo hai cách lấy mẫu:
       - theo bản ghi (coi 325 bản ghi độc lập; chỉ để đối chiếu, có thể quá lạc quan);
       - theo cụm truy vấn (lấy mẫu các truy vấn duy nhất, giữ nguyên mọi bản ghi của truy vấn đó); đây là phân tích chính.
  4. Các chẩn đoán phụ dùng trong phần thảo luận.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics as st
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

SEED = 20260928
RESAMPLES = 10_000
KS = ("1", "5", "10")
METRICS = ("precision", "recall", "f1")
LECTURE_CUES = ("giảng viên", "giang vien", "buổi", "buoi", "video", "slide", "bài giảng", "bai giang", "timestamp", "phút", "phut", "lectur")


def read(name: str, directory: str | None) -> bytes:
    if directory:
        return (Path(directory) / name).read_bytes()
    return subprocess.check_output(["git", "show", f"HEAD:evals/results/{name}"])


def load_json(system: str, directory: str | None) -> dict:
    return json.loads(read(f"{system}_retrieval_metrics.json", directory))


def load_rows(system: str, directory: str | None) -> dict[str, dict]:
    lines = read(f"{system}_retrieval_results.jsonl", directory).decode("utf-8").splitlines()
    return {r["question_id"]: r for r in (json.loads(l) for l in lines if l.strip())}


def ci95(samples: list[float]) -> tuple[float, float]:
    samples = sorted(samples)
    return samples[int(0.025 * len(samples)) - 1], samples[int(0.975 * len(samples)) - 1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=None, help="thư mục chứa các tệp kết quả")
    parser.add_argument("--json", default=None, help="ghi kết quả ra file JSON")
    args = parser.parse_args()

    base, prop = load_json("baseline", args.dir), load_json("proposed", args.dir)
    rb, rp = load_rows("baseline", args.dir), load_rows("proposed", args.dir)
    pb = {r["question_id"]: r["metrics"] for r in base["per_question"]}
    pp = {r["question_id"]: r["metrics"] for r in prop["per_question"]}
    assert set(pb) == set(pp), "hai hệ thống phải được chấm trên cùng tập câu hỏi"
    ids = sorted(pb)
    key = lambda q: (rb[q]["course_id"], rb[q]["question"])

    out: dict = {
        "n_records_total": len(rb),
        "n_questions_scored": len(ids),
        "counts": base["counts"],
        "corpus_coverage_rate": base["corpus_coverage"]["rate"],
        "n_missing_resources": len(base["corpus_coverage"]["missing_resource_ids"]),
        "macro": {"baseline": base["macro_average_answerable"], "proposed": prop["macro_average_answerable"]},
    }

    evidence = [pb[i]["1"]["total_ground_truth"] for i in ids]
    out["evidence_per_question"] = {
        "distribution": dict(sorted(Counter(evidence).items())),
        "mean": st.mean(evidence),
        "single_evidence_records": sum(1 for e in evidence if e == 1),
    }
    out["hit_rate"] = {
        name: {k: sum(m[i][k]["relevant_results"] > 0 for i in ids) / len(ids) for k in KS}
        for name, m in (("baseline", pb), ("proposed", pp))
    }

    # --- Mức độ lặp lại của câu hỏi ---
    groups: dict[tuple, list[str]] = defaultdict(list)
    for q in ids:
        groups[key(q)].append(q)
    repeated = {k: v for k, v in groups.items() if len(v) > 1}

    def chunk_ids(rows: dict, q: str) -> list[str]:
        return [x["chunk_id"] for x in rows[q]["results"]]

    identical = sum(
        all(chunk_ids(rb, v[0]) == chunk_ids(rb, q) and chunk_ids(rp, v[0]) == chunk_ids(rp, q) for q in v)
        for v in repeated.values()
    )
    differing_labels = sum(
        len({(json.dumps(pb[q]["10"], sort_keys=True), pb[q]["1"]["total_ground_truth"]) for q in v}) > 1 for v in repeated.values()
    )
    out["duplicates"] = {
        "distinct_question_strings_all_400": len({r["question"] for r in rb.values()}),
        "distinct_queries_among_scored": len(groups),
        "repeated_groups": len(repeated),
        "records_in_repeated_groups": sum(len(v) for v in repeated.values()),
        "group_size_distribution": dict(sorted(Counter(len(v) for v in repeated.values()).items())),
        "groups_with_identical_retrieval_lists": identical,
        "groups_with_differing_labels_or_scores": differing_labels,
    }

    # --- Bootstrap ghép cặp ---
    def diff(metric: str, k: str, records: list[str]) -> float:
        return st.mean(pp[i][k][metric] - pb[i][k][metric] for i in records)

    random.seed(SEED)  # theo bản ghi (giữ đúng dãy số ngẫu nhiên của lần tính đầu tiên)
    rec_res: dict = {}
    for k in KS:
        for metric in METRICS:
            obs = diff(metric, k, ids)
            lo, hi = ci95([diff(metric, k, [random.choice(ids) for _ in ids]) for _ in range(RESAMPLES)])
            rec_res[f"{metric}@{k}"] = {"diff": obs, "ci95": [lo, hi], "ci_excludes_zero": bool(lo > 0 or hi < 0)}

    rng = random.Random(SEED)  # theo cụm truy vấn
    clusters = list(groups.values())
    clu_res: dict = {}
    for k in KS:
        for metric in METRICS:
            obs = diff(metric, k, ids)
            samples = []
            for _ in range(RESAMPLES):
                recs = [i for c in rng.choices(clusters, k=len(clusters)) for i in c]
                samples.append(diff(metric, k, recs))
            lo, hi = ci95(samples)
            clu_res[f"{metric}@{k}"] = {"diff": obs, "ci95": [lo, hi], "ci_excludes_zero": bool(lo > 0 or hi < 0)}
    out["bootstrap"] = {
        "seed": SEED, "resamples": RESAMPLES,
        "record_level": rec_res,
        "cluster_level": clu_res,
        "n_clusters": len(clusters),
    }

    # --- Chẩn đoán phụ ---
    single = [q for q in ids if pb[q]["1"]["total_ground_truth"] == 1]
    lecture_all = [q for q in rb if any(c in rb[q]["question"].casefold() for c in LECTURE_CUES)]
    out["diagnostics"] = {
        "baseline_result_count_distribution": dict(sorted(Counter(len(r["results"]) for r in rb.values()).items())),
        "proposed_result_count_distribution": dict(sorted(Counter(len(r["results"]) for r in rp.values()).items())),
        "baseline_empty_records": sum(1 for r in rb.values() if not r["results"]),
        "baseline_empty_distinct_questions": len({r["question"] for r in rb.values() if not r["results"]}),
        "single_evidence_records_with_2plus_relevant": {
            name: {k: sum(M[q][k]["relevant_results"] >= 2 for q in single) for k in ("5", "10")}
            for name, M in (("baseline", pb), ("proposed", pp))
        },
        "records_with_lecture_cue_all_400": len(lecture_all),
        "records_with_lecture_cue_scored": len([q for q in ids if q in set(lecture_all)]),
    }

    print(f"Bản ghi: {out['n_records_total']} | được chấm: {len(ids)} | coverage: {out['corpus_coverage_rate']:.4%}")
    d = out["duplicates"]
    print(f"Câu hỏi khác nhau: {d['distinct_question_strings_all_400']}/400 (tất cả) ; {d['distinct_queries_among_scored']}/{len(ids)} (được chấm)")
    print(f"Nhóm lặp: {d['repeated_groups']} nhóm, {d['records_in_repeated_groups']} bản ghi, kích thước {d['group_size_distribution']}; "
          f"kết quả giống hệt: {d['groups_with_identical_retrieval_lists']}/{d['repeated_groups']}; nhãn khác nhau: {d['groups_with_differing_labels_or_scores']}/{d['repeated_groups']}")
    print("\nMacro (baseline | proposed):")
    for k in base["macro_average_answerable"]:
        print(f"  {k:>13}: {base['macro_average_answerable'][k]:.4f} | {prop['macro_average_answerable'][k]:.4f}")
    print("\nHit rate:", json.dumps(out["hit_rate"]))
    print("Evidence/bản ghi:", out["evidence_per_question"])
    print(f"\nBootstrap ghép cặp (seed={SEED}, {RESAMPLES} lần), proposed - baseline:")
    print(f"  {'':>13}  {'THEO BẢN GHI (325)':<44}THEO CỤM TRUY VẤN ({len(clusters)})  <- phân tích chính")
    for m in rec_res:
        a, b = rec_res[m], clu_res[m]
        fa = "KHÔNG chứa 0" if a["ci_excludes_zero"] else "chứa 0"
        fb = "KHÔNG chứa 0" if b["ci_excludes_zero"] else "chứa 0"
        print(f"  {m:>13}: {a['diff']:+.4f} [{a['ci95'][0]:+.4f}; {a['ci95'][1]:+.4f}] {fa:<13} | [{b['ci95'][0]:+.4f}; {b['ci95'][1]:+.4f}] {fb}")
    print("\nChẩn đoán:", json.dumps(out["diagnostics"], ensure_ascii=False))

    if args.json:
        Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nĐã ghi {args.json}")


if __name__ == "__main__":
    main()
