from __future__ import annotations

import re

from app.models.retrieval import RetrievalResult

_SPLIT = re.compile(r"(?<=[\.!?。…])\s+|\n+")


def tokenize(text: str) -> set[str]:
    from app.retrieval.retriever import process_user_query

    cleaned = process_user_query(text).casefold()
    return {token for token in re.split(r"\W+", cleaned, flags=re.UNICODE) if token}


def compress_hits(
    results: list[RetrievalResult],
    query: str,
    extra_queries: list[str] | None = None,
) -> list[RetrievalResult]:
    tokens = tokenize(query)
    for extra in extra_queries or []:
        tokens |= tokenize(extra)
    if not tokens:
        return list(results)
    out: list[RetrievalResult] = []
    for item in results:
        body = (item.content or "").strip()
        if not body or len(body) < 240:
            out.append(item)
            continue
        kept = [
            sent.strip()
            for sent in _SPLIT.split(body)
            if sent.strip() and tokenize(sent) & tokens
        ]
        if not kept:
            out.append(item)
            continue
        out.append(item.model_copy(update={"content": " ".join(kept)}))
    return out
