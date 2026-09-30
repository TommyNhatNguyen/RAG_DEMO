from __future__ import annotations

import json
from pathlib import Path
from typing import Any

VIDEO_PIPELINE_VERSION = "v2-long"
DURATION_TOLERANCE = 1.0

STAGES = (
    "metadata",
    "audio",
    "transcript",
    "coarse_frames",
    "selected",
    "indexed",
)


class VideoCheckpoint:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def update(self, **fields: Any) -> None:
        new_stage = fields.get("stage")
        if new_stage is not None and new_stage in STAGES and self.stage in STAGES:
            if STAGES.index(new_stage) < STAGES.index(self.stage):
                # Never move a stage backwards: a step re-running during a
                # resume (e.g. audio re-extracted after an "indexed"
                # checkpoint) must not make later reached() checks think
                # transcript/frames still need to be redone.
                fields = {key: value for key, value in fields.items() if key != "stage"}
        self.data.update(fields)
        self.save()

    @property
    def stage(self) -> str:
        return str(self.data.get("stage") or "")

    def reached(self, stage: str) -> bool:
        if stage not in STAGES or self.stage not in STAGES:
            return False
        return STAGES.index(self.stage) >= STAGES.index(stage)

    def matches(self, video_id: str, processed_duration: float) -> bool:
        if self.data.get("video_id") != video_id:
            return False
        if self.data.get("pipeline_version") != VIDEO_PIPELINE_VERSION:
            return False
        previous = self.data.get("processed_duration")
        if previous is None:
            return False
        return abs(float(previous) - float(processed_duration)) <= DURATION_TOLERANCE
