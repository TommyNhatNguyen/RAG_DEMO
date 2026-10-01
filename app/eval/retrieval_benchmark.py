from __future__ import annotations

import hashlib
import json
import math
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.models.retrieval import RetrievalResult

K_VALUES = (1, 5, 10)
_DASH_RE = re.compile(r"\s*[–—-]\s*")


@dataclass(frozen=True)
class RetrievalInput:
    question_id: str
    question: str
    course_id: str | None


def prepare_query_file(question_path: str | Path, output_path: str | Path) -> int:
    """Create the only file that a retrieval run is allowed to read.

    Ground-truth fields such as evidence and answerable are deliberately not
    represented by RetrievalInput and therefore cannot be passed to the RAG.
    """

    source = Path(question_path)
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Question draft must be a JSON array")
    inputs: list[RetrievalInput] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Question {index}: expected an object")
        question = str(item.get("question") or "").strip()
        if not question:
            raise ValueError(f"Question {index}: question is required")
        course = item.get("course_id")
        inputs.append(
            RetrievalInput(
                question_id=f"Q{index:03d}",
                question=question,
                course_id=str(course).strip() if course else None,
            )
        )
    _write_jsonl(
        output_path,
        (
            {
                "question_id": item.question_id,
                "question": item.question,
                "course_id": item.course_id,
            }
            for item in inputs
        ),
    )
    return len(inputs)


def load_query_file(path: str | Path) -> list[RetrievalInput]:
    rows = _load_jsonl(path)
    inputs: list[RetrievalInput] = []
    allowed = {"question_id", "question", "course_id"}
    for line_no, row in enumerate(rows, start=1):
        extra = set(row) - allowed
        if extra:
            raise ValueError(
                f"{path}:{line_no}: retrieval input contains forbidden fields: "
                + ", ".join(sorted(extra))
            )
        question_id = str(row.get("question_id") or "").strip()
        question = str(row.get("question") or "").strip()
        if not question_id or not question:
            raise ValueError(f"{path}:{line_no}: question_id and question are required")
        course = row.get("course_id")
        inputs.append(
            RetrievalInput(
                question_id=question_id,
                question=question,
                course_id=str(course).strip() if course else None,
            )
        )
    if len({item.question_id for item in inputs}) != len(inputs):
        raise ValueError("Duplicate question_id in retrieval input")
    return inputs


def run_retrieval(
    retriever: Any,
    inputs: list[RetrievalInput],
    output_path: str | Path,
    *,
    system_id: str,
    top_k: int = 10,
    include_visual: bool,
    use_course_filter: bool = True,
    resume: bool = False,
    query_set_hash: str | None = None,
    retrieve_fn: Any = None,
) -> dict[str, Any]:
    """`retrieve_fn`, if given, replaces the default bare `retriever.search(...)`
    call — e.g. `GenerationService.retrieve_for_eval` to exercise the real
    query-enhance/HyDE/iterative-loop pipeline instead of only hybrid+rerank.
    Signature: `retrieve_fn(question, k, include_visual, course) -> list[RetrievalResult]`.
    """
    if top_k < max(K_VALUES):
        raise ValueError("top_k must be at least 10 for P/R/F1@10")
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    completed: set[str] = set()
    mode = "w"
    if resume and target.exists():
        prior = _load_jsonl(target)
        completed = {
            str(row.get("question_id"))
            for row in prior
            if row.get("system_id") == system_id
        }
        mode = "a"
    query_hash = query_set_hash or query_set_sha256(inputs)
    written = 0
    failed = 0
    with target.open(mode, encoding="utf-8") as stream:
        for item in inputs:
            if item.question_id in completed:
                continue
            started = time.perf_counter()
            error: str | None = None
            try:
                # Only the learner question and optional course context reach RAG.
                course = item.course_id if use_course_filter else None
                if retrieve_fn is not None:
                    hits = retrieve_fn(item.question, top_k, include_visual, course)
                else:
                    hits = retriever.search(
                        item.question,
                        k=top_k,
                        include_visual=include_visual,
                        course=course,
                    )
            except Exception as exc:  # keep a long benchmark resumable
                hits = []
                error = f"{type(exc).__name__}: {exc}"
                failed += 1
            elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
            row = {
                "question_id": item.question_id,
                "system_id": system_id,
                "query_set_sha256": query_hash,
                "question": item.question,
                "course_id": item.course_id,
                "top_k": top_k,
                "elapsed_ms": elapsed_ms,
                "results": [
                    serialize_hit(item.question_id, rank, hit)
                    for rank, hit in enumerate(hits[:top_k], start=1)
                ],
            }
            if error:
                row["error"] = error
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            written += 1
    return {
        "system_id": system_id,
        "query_set_sha256": query_hash,
        "requested": len(inputs),
        "written": written,
        "resumed": len(completed),
        "failed": failed,
        "output": str(target.resolve()),
    }


def serialize_hit(
    question_id: str, rank: int, hit: RetrievalResult
) -> dict[str, Any]:
    meta = hit.metadata or {}
    relative_path = str(
        meta.get("relative_path") or meta.get("source") or meta.get("filename") or ""
    )
    resource_id = canonical_resource_id(relative_path)
    file_type = str(meta.get("file_type") or Path(resource_id).suffix).lower().lstrip(".")
    page_number = _int_or_none(meta.get("page_number", meta.get("page")))
    page: int | None = None
    slide: int | None = None
    if file_type in {"ppt", "pptx"}:
        slide = page_number
    elif file_type in {"pdf", "docx"}:
        page = page_number
    return {
        "question_id": question_id,
        "rank": rank,
        "resource_id": resource_id,
        "resource_type": resource_type(file_type, hit.content_type),
        "content_type": hit.content_type,
        "chunk_id": hit.id,
        "object_id": meta.get("document_id"),
        "page": page,
        "slide": slide,
        "start_time": _float_or_none(meta.get("start_time")),
        "end_time": _float_or_none(meta.get("end_time")),
        "retrieval_score": float(hit.score),
        "cosine_score": _float_or_none(meta.get("cosine")),
    }


def score_retrieval_file(
    question_path: str | Path,
    result_path: str | Path,
    *,
    null_policy: str = "infer",
    indexed_resource_ids: set[str] | None = None,
    resource_id_aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    questions = json.loads(Path(question_path).read_text(encoding="utf-8"))
    if not isinstance(questions, list):
        raise ValueError("Question draft must be a JSON array")
    result_rows = _load_jsonl(result_path)
    by_id = {str(row.get("question_id")): row for row in result_rows}
    if len(by_id) != len(result_rows):
        raise ValueError("Duplicate question_id in retrieval results")

    scored: list[dict[str, Any]] = []
    unanswerable_rows: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    inferred_answerable = 0
    inferred_unanswerable = 0
    missing_results: list[str] = []
    unavailable_ground_truth: list[dict[str, Any]] = []
    indexed = (
        {canonical_resource_id(value) for value in indexed_resource_ids}
        if indexed_resource_ids is not None
        else None
    )

    for index, question in enumerate(questions, start=1):
        question_id = f"Q{index:03d}"
        result_row = by_id.get(question_id)
        if result_row is None:
            missing_results.append(question_id)
            continue
        category = question.get("category")
        difficulty = question.get("difficulty")
        evidence = question.get("evidence") or []
        label = question.get("answerable")
        if label is None:
            if null_policy == "exclude":
                excluded.append(
                    {
                        "question_id": question_id,
                        "reason": "answerable is null",
                        "category": category,
                        "difficulty": difficulty,
                    }
                )
                continue
            if null_policy == "error":
                raise ValueError(f"{question_id}: answerable is null")
            if null_policy != "infer":
                raise ValueError("null_policy must be infer, exclude, or error")
            label = bool(evidence)
            if label:
                inferred_answerable += 1
            else:
                inferred_unanswerable += 1

        if label is False:
            unanswerable_rows.append(result_row)
            continue
        if not evidence:
            excluded.append(
                {
                    "question_id": question_id,
                    "reason": "no ground-truth evidence",
                    "category": category,
                    "difficulty": difficulty,
                }
            )
            continue
        if indexed is not None:
            missing_resources = sorted(
                {
                    resolve_evidence_resource_id(
                        str(item.get("resource_id") or ""), resource_id_aliases
                    )
                    for item in evidence
                }
                - indexed
            )
            if missing_resources:
                entry = {
                    "question_id": question_id,
                    "reason": "ground-truth resource is not indexed",
                    "missing_resources": missing_resources,
                    "category": category,
                    "difficulty": difficulty,
                }
                excluded.append(entry)
                unavailable_ground_truth.append(entry)
                continue
        results = list(result_row.get("results") or [])
        metrics = {
            str(k): metrics_at_k(evidence, results, k, resource_id_aliases)
            for k in K_VALUES
        }
        scored.append(
            {
                "question_id": question_id,
                "metrics": metrics,
                "category": category,
                "difficulty": difficulty,
            }
        )

    macro = {
        f"precision@{k}": _mean(
            [row["metrics"][str(k)]["precision"] for row in scored]
        )
        for k in K_VALUES
    }
    for k in K_VALUES:
        macro[f"recall@{k}"] = _mean(
            [row["metrics"][str(k)]["recall"] for row in scored]
        )
        macro[f"f1@{k}"] = _mean(
            [row["metrics"][str(k)]["f1"] for row in scored]
        )

    abstained = [row.get("abstained") for row in unanswerable_rows]
    observed_abstentions = [value for value in abstained if isinstance(value, bool)]
    rejection_rate = (
        sum(value is True for value in observed_abstentions) / len(observed_abstentions)
        if observed_abstentions
        else None
    )
    system_ids = sorted(
        {str(row.get("system_id")) for row in result_rows if row.get("system_id")}
    )
    query_hashes = sorted(
        {
            str(row.get("query_set_sha256"))
            for row in result_rows
            if row.get("query_set_sha256")
        }
    )
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "system_id": system_ids[0] if len(system_ids) == 1 else system_ids,
        "query_set_sha256": query_hashes[0] if len(query_hashes) == 1 else query_hashes,
        "k_values": list(K_VALUES),
        "label_policy": {
            "null_policy": null_policy,
            "inferred_answerable": inferred_answerable,
            "inferred_unanswerable": inferred_unanswerable,
        },
        "counts": {
            "questions": len(questions),
            "result_rows": len(result_rows),
            "answerable_scored": len(scored),
            "answerable_unscorable_missing_index": len(unavailable_ground_truth),
            "unanswerable_separate": len(unanswerable_rows),
            "excluded": len(excluded),
            "missing_results": len(missing_results),
        },
        "corpus_coverage": {
            "answerable_with_indexed_ground_truth": len(scored),
            "answerable_missing_indexed_ground_truth": len(unavailable_ground_truth),
            "rate": (
                len(scored) / (len(scored) + len(unavailable_ground_truth))
                if scored or unavailable_ground_truth
                else None
            ),
            "missing_resource_ids": sorted(
                {
                    resource
                    for row in unavailable_ground_truth
                    for resource in row["missing_resources"]
                }
            ),
        },
        "macro_average_answerable": macro,
        "by_category": _macro_by(scored, "category"),
        "by_difficulty": _macro_by(scored, "difficulty"),
        "excluded_by_category": _count_by(excluded, "category"),
        "excluded_by_difficulty": _count_by(excluded, "difficulty"),
        "resource_id_aliases_applied": len(resource_id_aliases or {}),
        "unanswerable_evaluation": {
            "n": len(unanswerable_rows),
            "retrieval_precision_recall_f1": None,
            "rejection_rate": rejection_rate,
            "rejection_rate_n": len(observed_abstentions),
            "note": (
                "Unanswerable questions are excluded from retrieval P/R/F1 because "
                "their relevant-evidence set is empty. Rejection rate requires an "
                "explicit boolean `abstained` decision from the answering system."
            ),
        },
        "per_question": scored,
        "excluded": excluded,
        "missing_question_ids": missing_results,
    }


def _macro_by(scored: list[dict[str, Any]], group_key: str) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in scored:
        buckets.setdefault(str(row.get(group_key) or "unknown"), []).append(row)
    out: dict[str, dict[str, Any]] = {}
    for label, rows in buckets.items():
        entry: dict[str, Any] = {"n": len(rows)}
        for k in K_VALUES:
            entry[f"precision@{k}"] = _mean([r["metrics"][str(k)]["precision"] for r in rows])
            entry[f"recall@{k}"] = _mean([r["metrics"][str(k)]["recall"] for r in rows])
            entry[f"f1@{k}"] = _mean([r["metrics"][str(k)]["f1"] for r in rows])
        out[label] = entry
    return dict(sorted(out.items()))


def _count_by(rows: list[dict[str, Any]], group_key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get(group_key) or "unknown")
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def metrics_at_k(
    evidence: list[dict[str, Any]],
    results: list[dict[str, Any]],
    k: int,
    aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    top = results[:k]
    relevant_results = 0
    matched_evidence: set[int] = set()
    for result in top:
        matches = {
            index
            for index, expected in enumerate(evidence)
            if result_matches_evidence(result, expected, aliases)
        }
        if matches:
            relevant_results += 1
            matched_evidence.update(matches)
    precision = relevant_results / k
    recall = len(matched_evidence) / len(evidence)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "relevant_results": relevant_results,
        "matched_ground_truth": len(matched_evidence),
        "total_ground_truth": len(evidence),
    }


def load_resource_id_aliases(path: str | Path) -> dict[str, str]:
    """Static slug-spelling -> real-filename map for evidence resource_ids.

    Some question-draft files (e.g. questions_draft_v7.json) store an
    ASCII-slugified resource_id that never matches the accented/spaced
    filenames actually on disk (and thus in Chroma's `relative_path`).
    This is a small, fully-enumerable, human-reviewed table rather than a
    runtime fuzzy matcher, applied only on the evidence side.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return {
        canonical_resource_id(str(k)): canonical_resource_id(str(v))
        for k, v in data.items()
    }


def resolve_evidence_resource_id(value: str, aliases: dict[str, str] | None = None) -> str:
    canonical = canonical_resource_id(value)
    if not aliases:
        return canonical
    return aliases.get(canonical, canonical)


def result_matches_evidence(
    result: dict[str, Any],
    expected: dict[str, Any],
    aliases: dict[str, str] | None = None,
) -> bool:
    if canonical_resource_id(str(result.get("resource_id") or "")) != resolve_evidence_resource_id(
        str(expected.get("resource_id") or ""), aliases
    ):
        return False
    page = _int_or_none(expected.get("page"))
    if page is not None and _int_or_none(result.get("page")) != page:
        return False
    slide = _int_or_none(expected.get("slide"))
    if slide is not None and _int_or_none(result.get("slide")) != slide:
        return False
    timestamp = expected.get("timestamp")
    if timestamp:
        expected_start, expected_end = parse_timestamp_range(str(timestamp))
        result_start = _float_or_none(result.get("start_time"))
        result_end = _float_or_none(result.get("end_time"))
        if result_start is None or result_end is None:
            return False
        if max(expected_start, result_start) > min(expected_end, result_end):
            return False
    return True


def parse_timestamp_range(value: str) -> tuple[float, float]:
    parts = _DASH_RE.split(value.strip(), maxsplit=1)
    if len(parts) != 2:
        raise ValueError(f"Invalid timestamp range: {value}")
    return _parse_clock(parts[0]), _parse_clock(parts[1])


def _parse_clock(value: str) -> float:
    parts = value.strip().split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours, minutes, seconds = "0", parts[0], parts[1]
    else:
        return float(parts[0])
    return float(hours) * 3600.0 + float(minutes) * 60.0 + float(seconds)


def canonical_resource_id(value: str) -> str:
    text = unicodedata.normalize("NFC", value.replace("\\", "/").strip())
    marker = "/RAG_DEMO/"
    if marker in text:
        text = "RAG_DEMO/" + text.split(marker, 1)[1]
    text = text.lstrip("./")
    if text.startswith("assets/"):
        text = "RAG_DEMO/" + text
    return text


def resource_type(file_type: str, content_type: str) -> str:
    if file_type in {"mp4", "mov", "mkv", "avi", "webm", "m4v"}:
        return "video"
    if file_type in {"ppt", "pptx"}:
        return "slide"
    if file_type == "pdf":
        return "pdf"
    if file_type == "docx":
        return "docx"
    if content_type in {"image", "page"}:
        return "image"
    return file_type or "unknown"


def query_set_sha256(inputs: list[RetrievalInput]) -> str:
    payload = "\n".join(
        json.dumps(
            {
                "question_id": item.question_id,
                "question": item.question,
                "course_id": item.course_id,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        for item in inputs
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no}: expected an object")
        rows.append(row)
    return rows


def _write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None
