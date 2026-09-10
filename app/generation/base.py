from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol


class Generator(Protocol):
    def generate(self, query: str, *, k: int | None = None, include_visual: bool = True) -> str: ...

    def stream(self, query: str, *, k: int | None = None, include_visual: bool = True) -> Iterator[str]: ...
