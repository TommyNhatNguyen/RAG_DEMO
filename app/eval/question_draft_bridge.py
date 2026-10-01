from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.eval.retrieval_benchmark import resolve_evidence_resource_id


def _strip_rag_demo_prefix(value: str) -> str:
    """`retrieval_benchmark.py` canonicalizes evidence resource_ids to
    `RAG_DEMO/assets/...`; `app/eval/golden.py` / `app/eval/metrics.py`
    (and this repo's real `relative_path` metadata) use bare `assets/...`.
    Bridge between the two conventions."""
    if value.startswith("RAG_DEMO/"):
        return value[len("RAG_DEMO/") :]
    return value


def question_draft_to_golden_jsonl(
    question_path: str | Path,
    output_path: str | Path,
    *,
    aliases: dict[str, str] | None = None,
) -> int:
    """Convert a questions_draft*.json (400-question style) file into the
    `golden.jsonl` schema consumed by `app/eval/golden.py::load_golden()`,
    for the generation-level (`python -m app.main eval`) pass. There is no
    reference answer in the source file, so `ground_truth` is left empty —
    `app/eval/runner.py::_llm_scores()` detects this and switches to a
    reference-free judge automatically."""
    data = json.loads(Path(question_path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Question draft must be a JSON array")

    rows: list[dict[str, Any]] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Question {index}: expected an object")
        question = str(item.get("question") or "").strip()
        if not question:
            raise ValueError(f"Question {index}: question is required")
        evidence = item.get("evidence") or []
        expected_paths: list[str] = []
        seen: set[str] = set()
        for entry in evidence:
            if not isinstance(entry, dict):
                continue
            resource_id = str(entry.get("resource_id") or "")
            if not resource_id:
                continue
            resolved = _strip_rag_demo_prefix(
                resolve_evidence_resource_id(resource_id, aliases)
            )
            if resolved and resolved not in seen:
                seen.add(resolved)
                expected_paths.append(resolved)
        rows.append(
            {
                "id": f"Q{index:03d}",
                "question": question,
                "ground_truth": "",
                "kind": item.get("category") or "theory",
                "course": item.get("course_id"),
                "expected_paths": expected_paths,
                "difficulty": item.get("difficulty"),
                "evidence": evidence,
            }
        )

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)
