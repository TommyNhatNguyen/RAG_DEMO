from __future__ import annotations

import re
import unicodedata

from app.generation.context import collect_source_paths
from app.ids import nfc
from app.index_manifest import IndexManifest
from app.models.retrieval import RetrievalResult

_CATALOG_CUES = (
    "lộ trình",
    "lo trinh",
    "tài liệu",
    "tai lieu",
    "giáo trình",
    "giao trinh",
    "môn ",
    "mon ",
    "chương trình",
    "chuong trinh",
    "danh sách",
    "danh sach",
)


def is_catalog_query(query: str) -> bool:
    lowered = (query or "").casefold()
    return any(cue in lowered for cue in _CATALOG_CUES)


def slug(text: str) -> str:
    folded = unicodedata.normalize("NFD", text or "")
    stripped = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", "", stripped.casefold())


def catalog_subqueries(original: str) -> list[str]:
    return [
        f"nội dung chương mục tiêu học tập {original}",
        f"danh sách tài liệu học liệu {original}",
    ]


def _query_phrases(query: str) -> list[str]:
    words = [slug(part) for part in re.split(r"\W+", query or "") if slug(part)]
    phrases: list[str] = []
    for start in range(len(words)):
        acc = ""
        for word in words[start:]:
            acc += word
            if len(acc) >= 8:
                phrases.append(acc)
    full = slug(query)
    if full:
        phrases.append(full)
    return phrases


def match_manifest_paths(manifest: IndexManifest | None, query: str) -> list[str]:
    if manifest is None:
        return []
    phrases = _query_phrases(query)
    if not phrases:
        return []
    paths: list[str] = []
    for path in manifest.indexed_paths():
        rel = nfc(path)
        parts = [part for part in rel.replace("\\", "/").split("/") if part]
        course = (
            parts[1]
            if len(parts) >= 2 and parts[0] == "assets"
            else (parts[0] if parts else "")
        )
        folder = slug(course)
        if not folder:
            continue
        if any(phrase in folder or folder in phrase for phrase in phrases):
            paths.append(rel)
    return paths


def merge_source_paths(hits: list[RetrievalResult], extra: list[str]) -> str:
    base = collect_source_paths(hits)
    lines = [line for line in base.splitlines() if line.strip() and "không có" not in line]
    seen = {nfc(line.lstrip("- ").strip()) for line in lines}
    for path in extra:
        key = nfc(path)
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"- {path}")
    return "\n".join(lines) if lines else base
