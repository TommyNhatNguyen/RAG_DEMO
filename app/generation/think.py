from __future__ import annotations

OPEN_THINK = "<" + "think" + ">"
CLOSE_THINK = "</" + "think" + ">"


def strip_think(text: str) -> str:
    """Drop leftover Qwen think blocks if any."""
    if not text:
        return ""
    if CLOSE_THINK in text:
        return text.rsplit(CLOSE_THINK, 1)[-1].strip()
    if OPEN_THINK in text:
        return ""
    return text.strip()


class ThinkStreamFilter:
    """Hide incomplete and complete <think> blocks while streaming tokens."""

    def __init__(self) -> None:
        self.buf = ""
        self.visible = ""
        self.in_think = False

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        self.buf += chunk
        emitted = ""
        while True:
            if self.in_think:
                end = self.buf.find(CLOSE_THINK)
                if end < 0:
                    if len(self.buf) > 8000:
                        self.buf = self.buf[-200:]
                    break
                self.buf = self.buf[end + len(CLOSE_THINK) :]
                self.in_think = False
                continue
            start = self.buf.find(OPEN_THINK)
            if start >= 0:
                out = self.buf[:start]
                if out:
                    emitted += out
                    self.visible += out
                self.buf = self.buf[start + len(OPEN_THINK) :]
                self.in_think = True
                continue
            hold = max(len(OPEN_THINK) - 1, 0)
            if len(self.buf) > hold:
                out, self.buf = self.buf[:-hold], self.buf[-hold:]
                emitted += out
                self.visible += out
            break
        return emitted

    def flush(self) -> str:
        if not self.in_think and self.buf:
            out = self.buf
            self.visible += out
            self.buf = ""
            return out
        return ""
