from __future__ import annotations

import logging
from typing import Any

from app.eval.metrics import METRIC_KEYS

logger = logging.getLogger(__name__)


def score_with_ragas(
    traces: list[dict[str, Any]],
    *,
    llm: Any | None = None,
    embeddings: Any | None = None,
) -> dict[str, float | None]:
    try:
        from ragas import EvaluationDataset, evaluate
        from ragas.dataset_schema import SingleTurnSample
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import (
            Faithfulness,
            LLMContextPrecisionWithReference,
            LLMContextRecall,
            ResponseRelevancy,
        )
    except ImportError:
        logger.warning('RAGAs extra missing. Install with: pip install -e ".[eval]"')
        return {}

    samples: list[Any] = []
    for trace in traces:
        if not (trace.get("answer") or "").strip():
            continue
        samples.append(
            SingleTurnSample(
                user_input=str(trace.get("question") or ""),
                retrieved_contexts=list(trace.get("contexts") or []),
                response=str(trace.get("answer") or ""),
                reference=str(trace.get("ground_truth") or ""),
            )
        )
    if not samples:
        return {}

    kwargs: dict[str, Any] = {
        "dataset": EvaluationDataset(samples=samples),
        "metrics": [
            Faithfulness(),
            LLMContextPrecisionWithReference(),
            LLMContextRecall(),
            ResponseRelevancy(),
        ],
    }
    if llm is not None:
        try:
            kwargs["llm"] = LangchainLLMWrapper(llm)
        except Exception:
            logger.exception("RAGAs LLM wrapper failed")
            return {}
    if embeddings is not None:
        kwargs["embeddings"] = embeddings
    try:
        result = evaluate(**kwargs)
    except Exception:
        logger.exception("RAGAs evaluate failed")
        return {}
    scores = _as_dict(result)
    mapped = {
        "faithfulness": _pick(scores, "faithfulness"),
        "answer_relevancy": _pick(scores, "answer_relevancy", "response_relevancy", "answer_relevancy"),
        "context_precision": _pick(scores, "llm_context_precision_with_reference", "context_precision"),
        "context_recall": _pick(scores, "llm_context_recall", "context_recall"),
    }
    return {key: mapped.get(key) for key in METRIC_KEYS}


def _as_dict(result: Any) -> dict[str, Any]:
    if hasattr(result, "to_pandas"):
        try:
            frame = result.to_pandas()
            means = frame.mean(numeric_only=True)
            return {str(k): float(v) for k, v in means.items()}
        except Exception:
            pass
    if isinstance(result, dict):
        return result
    scores = getattr(result, "scores", None)
    if isinstance(scores, dict):
        return scores
    return {}


def _pick(scores: dict[str, Any], *names: str) -> float | None:
    lowered = {str(key).lower(): value for key, value in scores.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None
