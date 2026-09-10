from __future__ import annotations

import time
from logging import Logger


def progress_step(total: int, every: int | None = None) -> int:
    if every is not None:
        return max(1, every)
    if total <= 0:
        return 1
    return max(1, total // 10)


def should_log_progress(
    done: int,
    total: int,
    *,
    every: int | None = None,
    prev: int | None = None,
) -> bool:
    if done <= 0 or (total > 0 and done >= total):
        return True
    if total <= 0:
        return False
    step = progress_step(total, every)
    before = done - 1 if prev is None else max(prev, 0)
    return (done // step) > (before // step)


def log_progress(
    logger: Logger,
    label: str,
    done: int,
    total: int,
    *,
    every: int | None = None,
    started: float | None = None,
    prev: int | None = None,
) -> None:
    if not should_log_progress(done, total, every=every, prev=prev):
        return
    pct = 0 if total <= 0 else min(100, int(round(100.0 * done / total)))
    extra = ""
    if started is not None:
        extra = f" elapsed={time.perf_counter() - started:.0f}s"
    logger.info("%s %s/%s (%s%%)%s", label, done, total, pct, extra)
