"""Immutable render plans produced before any external process is started."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from videoos.core.models import TargetSpec, TransformSpec


@dataclass(frozen=True, slots=True)
class RenderOperation:
    """One validated source range and its deterministic visual/audio treatment."""

    source_id: str
    source_path: Path
    input_index: int
    source_start: float
    source_end: float
    transform: TransformSpec | None
    has_audio: bool

    @property
    def duration_seconds(self) -> float:
        return self.source_end - self.source_start


@dataclass(frozen=True, slots=True)
class RenderPlan:
    """A pure FFmpeg invocation plan; building it does not create any files."""

    argv: tuple[str, ...]
    filter_graph: str
    operations: tuple[RenderOperation, ...]
    expected_duration_seconds: float
    warnings: tuple[str, ...]
    output: Path
    temp_output: Path
    input_paths: tuple[Path, ...]
    target: TargetSpec
    caption_file: Path | None
    has_audio: bool
    video_codec: str


@dataclass(frozen=True, slots=True)
class RenderResult:
    """The bounded outcome of a dry-run or completed local render."""

    plan: RenderPlan
    output: Path | None
    dry_run: bool
    diagnostics: str
