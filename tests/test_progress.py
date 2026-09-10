import logging

from app.progress import log_progress, should_log_progress


def test_should_log_start_and_end():
    assert should_log_progress(0, 100)
    assert should_log_progress(100, 100)
    assert should_log_progress(240, 240)


def test_should_log_every_10_percent_not_every_item():
    hits = [done for done in range(1, 100) if should_log_progress(done, 100)]
    assert 10 in hits
    assert 50 in hits
    assert 1 not in hits
    assert 9 not in hits
    assert hits == [10, 20, 30, 40, 50, 60, 70, 80, 90]


def test_every_n_overrides_percent():
    hits = [done for done in range(1, 21) if should_log_progress(done, 20, every=5)]
    assert hits == [5, 10, 15, 20]


def test_should_log_when_batch_jumps_past_percent():
    assert not should_log_progress(32, 408, prev=0)
    assert should_log_progress(64, 408, prev=32)


def test_log_progress_writes_expected_message(caplog):
    logger = logging.getLogger("test.progress")
    with caplog.at_level(logging.INFO, logger="test.progress"):
        log_progress(logger, "Embedding frames", 0, 240)
        log_progress(logger, "Embedding frames", 1, 240)
        log_progress(logger, "Embedding frames", 24, 240)
        log_progress(logger, "Embedding frames", 240, 240)
    messages = [record.getMessage() for record in caplog.records]
    assert messages[0] == "Embedding frames 0/240 (0%)"
    assert "Embedding frames 1/240" not in "".join(messages)
    assert "Embedding frames 24/240 (10%)" in messages
    assert messages[-1] == "Embedding frames 240/240 (100%)"
