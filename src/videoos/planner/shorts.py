"""Bounded, non-semantic short-form candidate selection."""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

from videoos.analysis.models import AnalysisArtifact, SpeechRegion
from videoos.core.time import finite_non_negative

CandidateReason = Literal["transcript-window", "speech-window", "scene-window", "heuristic-window"]
_MIN_DURATION_SECONDS = 15.0
_MAX_DURATION_SECONDS = 60.0


@dataclass(frozen=True)
class ShortCandidate:
    source_start: float
    source_end: float
    score: float
    title: str
    reason: CandidateReason

    def __post_init__(self) -> None:
        start = finite_non_negative(self.source_start, "source_start")
        end = finite_non_negative(self.source_end, "source_end")
        score = float(self.score)
        if end < start:
            raise ValueError("source_end must be greater than or equal to source_start")
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("score must be finite and between 0 and 1")
        if not self.title:
            raise ValueError("title must be non-empty")
        object.__setattr__(self, "source_start", start)
        object.__setattr__(self, "source_end", end)
        object.__setattr__(self, "score", score)

    @property
    def duration_seconds(self) -> float:
        return self.source_end - self.source_start


def _duration(analysis: AnalysisArtifact) -> float:
    duration = analysis.probe.duration
    if duration is None or not math.isfinite(duration) or duration < 0:
        raise ValueError("analysis requires a finite non-negative media duration")
    return float(duration)


def _window_around(start: float, end: float, duration: float) -> tuple[float, float]:
    window_duration = min(_MAX_DURATION_SECONDS, duration)
    if duration <= _MIN_DURATION_SECONDS:
        return 0.0, duration
    desired = max(_MIN_DURATION_SECONDS, min(window_duration, max(end - start, _MIN_DURATION_SECONDS)))
    centered_start = max(0.0, min(duration - desired, (start + end - desired) / 2))
    return centered_start, centered_start + desired


def _speech_overlap(start: float, end: float, regions: list[SpeechRegion]) -> float:
    return sum(max(0.0, min(end, region.end) - max(start, region.start)) for region in regions)


def _score(start: float, end: float, regions: list[SpeechRegion], scene_times: set[float]) -> float:
    duration = end - start
    if duration <= 0:
        return 0.0
    density = min(1.0, _speech_overlap(start, end, regions) / duration)
    fit = 1.0 - min(1.0, abs(min(duration, _MAX_DURATION_SECONDS) - 37.5) / 37.5)
    boundary = 1.0 if start in scene_times or end in scene_times else 0.0
    hook = 1.0 if any(start <= region.start <= start + 3.0 for region in regions) else 0.0
    return max(0.0, min(1.0, 0.55 * density + 0.25 * fit + 0.15 * boundary + 0.05 * hook))


def _scene_windows(scene_times: list[float], duration: float) -> list[tuple[float, float]]:
    windows: list[tuple[float, float]] = []
    for start, end in pairwise(scene_times):
        if end > start:
            windows.append(_window_around(start, end, duration))
    return windows


def _transcript_windows(
    regions: list[SpeechRegion], scene_times: list[float], duration: float
) -> list[tuple[float, float]]:
    boundaries = sorted({0.0, duration, *scene_times})
    windows: list[tuple[float, float]] = []
    for region in regions:
        before = max((time for time in boundaries if time <= region.start), default=0.0)
        after = min((time for time in boundaries if time >= region.end), default=duration)
        windows.append(_window_around(before, after, duration))
    return windows


def _heuristic_windows(duration: float, count: int) -> list[tuple[float, float]]:
    window_duration = min(_MAX_DURATION_SECONDS, duration)
    if duration <= window_duration:
        return [(0.0, duration)]
    slots = max(1, count)
    starts = [
        min(index * (duration - window_duration) / max(1, slots - 1), duration - window_duration)
        for index in range(slots)
    ]
    return [(start, start + window_duration) for start in starts]


def score_short_candidates(analysis: AnalysisArtifact, *, count: int) -> list[ShortCandidate]:
    """Return deterministic 15–60 second candidates without semantic claims."""
    if count < 1:
        raise ValueError("count must be at least 1")
    duration = _duration(analysis)
    if duration == 0:
        return []
    regions = list(analysis.transcript.regions) if analysis.transcript is not None else []
    scene_times = sorted({time for time in (boundary.time for boundary in analysis.scene_boundaries) if 0 <= time <= duration})
    windows: list[tuple[float, float]]
    reason: CandidateReason
    if regions:
        windows = _transcript_windows(regions, scene_times, duration)
        reason = "transcript-window"
    elif scene_times:
        windows = _scene_windows(scene_times, duration)
        reason = "scene-window" if windows else "heuristic-window"
        if not windows:
            windows = _heuristic_windows(duration, count)
    else:
        windows = _heuristic_windows(duration, count)
        reason = "heuristic-window"
    scored_windows = [
        (start, end, _score(start, end, regions, set(scene_times))) for start, end in windows
    ]
    deduplicated = {(start, end): score for start, end, score in scored_windows}
    ordered = sorted(
        ((start, end, score) for (start, end), score in deduplicated.items()),
        key=lambda item: (-item[2], item[0], item[1]),
    )[:count]
    return [
        ShortCandidate(
            source_start=start,
            source_end=end,
            score=score,
            title=f"Short {index}",
            reason=reason,
        )
        for index, (start, end, score) in enumerate(ordered, start=1)
    ]
