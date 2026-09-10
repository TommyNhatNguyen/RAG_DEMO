from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GoldenItem:
    id: str
    question: str
    ground_truth: str
    kind: str = "theory"
    course: str | None = None
    source: str | None = None
    content_type: str | None = None
    expected_paths: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


def load_golden(path: str | Path) -> list[GoldenItem]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Golden set not found: {file_path}")
    items: list[GoldenItem] = []
    for line_no, raw in enumerate(file_path.read_text(encoding="utf-8").splitlines(), 1):
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{file_path}:{line_no}: invalid JSON") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{file_path}:{line_no}: expected object")
        question = str(data.get("question") or "").strip()
        if not question:
            raise ValueError(f"{file_path}:{line_no}: question is required")
        paths = data.get("expected_paths") or []
        if isinstance(paths, str):
            paths = [paths]
        if not isinstance(paths, list):
            raise ValueError(f"{file_path}:{line_no}: expected_paths must be a list")
        item_id = str(data.get("id") or f"q{line_no}")
        items.append(
            GoldenItem(
                id=item_id,
                question=question,
                ground_truth=str(data.get("ground_truth") or data.get("reference") or ""),
                kind=str(data.get("kind") or "theory"),
                course=data.get("course") or None,
                source=data.get("source") or None,
                content_type=data.get("content_type") or None,
                expected_paths=[str(p).strip() for p in paths if str(p).strip()],
                extra={
                    key: value
                    for key, value in data.items()
                    if key
                    not in {
                        "id",
                        "question",
                        "ground_truth",
                        "reference",
                        "kind",
                        "course",
                        "source",
                        "content_type",
                        "expected_paths",
                    }
                },
            )
        )
    return items
