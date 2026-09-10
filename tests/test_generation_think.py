from app.generation.think import ThinkStreamFilter, strip_think


def test_strip_think_drops_prefix_before_close():
    raw = "noise <think>secret</think> visible answer"
    assert strip_think(raw) == "visible answer"


def test_strip_think_open_without_close_is_empty():
    assert strip_think("hello <think>still thinking") == ""


def test_strip_think_plain_text():
    assert strip_think("  hello  ") == "hello"


def test_strip_think_empty():
    assert strip_think("") == ""
    assert strip_think(None) == ""  # type: ignore[arg-type]


def test_stream_filter_hides_think_across_chunks():
    filt = ThinkStreamFilter()
    chunks = ["He", "llo <th", "ink>secret</th", "ink> world"]
    visible = "".join(filt.feed(chunk) for chunk in chunks)
    visible += filt.flush()
    assert visible == "Hello  world"
    assert "secret" not in visible
    assert "<think>" not in visible
