"""Safe conversion helpers between source and assembled timeline timestamps."""

from __future__ import annotations

from collections.abc import Sequence

from videoos.core.time import TimeRange, finite_non_negative


def _merged_ranges(ranges: Sequence[TimeRange]) -> list[TimeRange]:
    merged: list[TimeRange] = []
    for item in sorted(ranges, key=lambda value: (value.start, value.end)):
        if merged and item.start <= merged[-1].end:
            merged[-1] = TimeRange(start=merged[-1].start, end=max(merged[-1].end, item.end))
        else:
            merged.append(item)
    return merged


def source_to_timeline(source_time: float, cuts: Sequence[TimeRange]) -> float | None:
    """Map a source time through removed ranges, returning None inside a cut."""
    source = finite_non_negative(source_time, "source_time")
    removed_before = 0.0
    for cut in _merged_ranges(cuts):
        if cut.start <= source <= cut.end:
            return None
        if cut.end < source:
            removed_before += cut.duration()
        else:
            break
    return source - removed_before


def timeline_to_source(timeline_time: float, kept: Sequence[TimeRange]) -> float:
    """Map a timeline time into its sequential source keep range."""
    timeline = finite_non_negative(timeline_time, "timeline_time")
    elapsed = 0.0
    for keep in _merged_ranges(kept):
        next_elapsed = elapsed + keep.duration()
        if timeline <= next_elapsed:
            return keep.start + (timeline - elapsed)
        elapsed = next_elapsed
    raise ValueError("timeline_time exceeds kept duration")
