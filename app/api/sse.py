from __future__ import annotations

import json
from typing import Any

from sse_starlette.sse import ServerSentEvent


def sse_event(name: str, data: dict[str, Any]) -> ServerSentEvent:
    return ServerSentEvent(event=name, data=json.dumps(data, ensure_ascii=False))
