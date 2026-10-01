#!/usr/bin/env python3
"""Tính lại số liệu sinh câu trả lời (generation-level) cho thực nghiệm bổ sung
trên bộ câu hỏi v7, từ `evals/reports/v7_generation.json` gốc.

Hệ thống: hybrid đa phương thức + bộ xếp hạng lại đã sửa, chỉ truy xuất văn bản
(`--text-only`), giám khảo tham chiếu-tự-do bằng chính Qwen3-1.7B (không có đáp
án chuẩn để so sánh).

Chạy từ gốc repo:
    python3 document/KLTN_MM-RAG/tools/generation_stats_v7.py
    python3 document/KLTN_MM-RAG/tools/generation_stats_v7.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import statistics as st
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default="evals/reports/v7_generation.json")
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    report = json.loads(Path(args.path).read_text(encoding="utf-8"))
    items = report["items"]

    out: dict = {"n": report["n"], "scores": report["scores"], "by_kind": report["by_kind"], "by_difficulty": report["by_difficulty"]}

    faith = [t["faithfulness"] for t in items if t.get("faithfulness") is not None]
    rel = [t["answer_relevancy"] for t in items if t.get("answer_relevancy") is not None]
    out["faithfulness_n_scored"] = len(faith)
    out["faithfulness_distribution"] = dict(sorted(Counter(round(x, 1) for x in faith).items()))
    out["answer_relevancy_n_scored"] = len(rel)
    out["answer_relevancy_distribution"] = dict(sorted(Counter(round(x, 1) for x in rel).items()))
    out["faithfulness_binary_share"] = sum(1 for x in faith if x in (0.0, 1.0)) / len(faith)

    cp = [t.get("citation_precision") for t in items if t.get("citation_precision") is not None]
    cr = [t.get("citation_recall") for t in items if t.get("citation_recall") is not None]
    cf1 = [t.get("citation_f1") for t in items if t.get("citation_f1") is not None]
    out["citation"] = {
        "n": len(cp),
        "precision_mean": st.mean(cp) if cp else None,
        "recall_mean": st.mean(cr) if cr else None,
        "f1_mean": st.mean(cf1) if cf1 else None,
    }

    print(f"n={out['n']}")
    print("scores:", json.dumps(out["scores"], ensure_ascii=False, indent=2))
    print(f"\nfaithfulness: n={out['faithfulness_n_scored']} distribution={out['faithfulness_distribution']}")
    print(f"  tỷ lệ chỉ nhận giá trị 0.0 hoặc 1.0: {out['faithfulness_binary_share']:.4f}")
    print(f"answer_relevancy: n={out['answer_relevancy_n_scored']} distribution={out['answer_relevancy_distribution']}")
    print(f"\ncitation: {json.dumps(out['citation'], ensure_ascii=False)}")
    print("\nby_kind (category):")
    for k, v in out["by_kind"].items():
        print(f"  {k}: {v}")
    print("\nby_difficulty:")
    for k, v in out["by_difficulty"].items():
        print(f"  {k}: {v}")

    if args.json:
        Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nĐã ghi {args.json}")


if __name__ == "__main__":
    main()
