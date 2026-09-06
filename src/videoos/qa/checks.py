"""Pure timeline and output invariant checks; media inspection happens elsewhere."""

from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path

from videoos.analysis.models import MediaProbe
from videoos.core.models import Timeline

from .models import QACheck, QAExpectation, QAStatus

_DURATION_TOLERANCE_SECONDS = 0.15
_AUDIO_PEAK_WARNING_DBFS = -1.0


def _check(name: str, status: QAStatus, message: str, **evidence: str | float | bool | None) -> QACheck:
    return QACheck(name=name, status=status, message=message, evidence=evidence or None)


def _finite(value: float | None) -> bool:
    return value is not None and math.isfinite(value)


def _finite_evidence(value: float | None) -> float | None:
    return value if _finite(value) else None


def check_timeline(timeline: Timeline, source_durations: Mapping[str, float]) -> list[QACheck]:
    """Report source bounds, ordering, continuous-video gaps, and caption bounds."""
    checks: list[QACheck] = []
    invalid_duration_sources = [
        source_id for source_id, duration in source_durations.items() if not _finite(duration) or duration < 0
    ]
    if invalid_duration_sources:
        checks.append(
            _check(
                "timeline.source_durations",
                "fail",
                "source durations must be finite and non-negative",
                source_ids=",".join(sorted(invalid_duration_sources)),
            )
        )
    else:
        checks.append(_check("timeline.source_durations", "pass", "source durations are finite"))

    bound_errors: list[str] = []
    overlap_tracks: list[str] = []
    gap_tracks: list[str] = []
    for track in timeline.tracks:
        previous_end = 0.0
        for segment in sorted(track.segments, key=lambda item: item.timeline_start):
            source_duration = source_durations.get(segment.source_id)
            if source_duration is None:
                bound_errors.append(f"unknown source {segment.source_id}")
            elif not _finite(source_duration) or source_duration < 0:
                bound_errors.append(f"invalid source duration {segment.source_id}")
            elif segment.source_end > source_duration:
                bound_errors.append(f"source range exceeds duration {segment.source_id}")
            if segment.timeline_start < previous_end:
                overlap_tracks.append(track.id)
            elif track.kind == "video" and segment.timeline_start > previous_end:
                gap_tracks.append(track.id)
            previous_end = max(previous_end, segment.timeline_end)

    checks.append(
        _check(
            "timeline.source_bounds",
            "fail" if bound_errors else "pass",
            "; ".join(bound_errors) if bound_errors else "all source ranges are within bounds",
        )
    )
    checks.append(
        _check(
            "timeline.track_overlaps",
            "fail" if overlap_tracks else "pass",
            f"overlaps in tracks: {', '.join(sorted(set(overlap_tracks)))}" if overlap_tracks else "tracks do not overlap",
        )
    )
    checks.append(
        _check(
            "timeline.track_gaps",
            "fail" if gap_tracks else "pass",
            f"gaps in continuous video tracks: {', '.join(sorted(set(gap_tracks)))}" if gap_tracks else "continuous video tracks have no gaps",
        )
    )

    duration = timeline.duration_seconds()
    caption_errors = [cue for cue in timeline.captions if cue.start < 0 or cue.end > duration]
    checks.append(
        _check(
            "timeline.caption_bounds",
            "fail" if caption_errors else "pass",
            "caption range exceeds timeline duration" if caption_errors else "caption cues are within timeline bounds",
            timeline_duration=duration,
        )
    )
    return checks


def check_output(path: Path, expected: QAExpectation, probe: MediaProbe) -> list[QACheck]:
    """Report output invariants from a caller-supplied local media probe."""
    output = Path(path)
    exists = output.is_file()
    checks = [
        _check("output.exists", "pass" if exists else "fail", "output exists" if exists else "output is missing"),
        _check(
            "output.nonzero_size",
            "pass" if exists and output.stat().st_size > 0 else "fail",
            "output has non-zero size" if exists and output.stat().st_size > 0 else "output is empty or missing",
        ),
    ]

    duration_matches = _finite(probe.duration) and (
        expected.duration is None or abs(probe.duration - expected.duration) <= _DURATION_TOLERANCE_SECONDS
    )
    checks.append(
        _check(
            "output.duration",
            "pass" if duration_matches else "fail",
            "output duration matches expectation" if duration_matches else "output duration is missing, non-finite, or outside tolerance",
            actual=_finite_evidence(probe.duration),
            expected=expected.duration,
            tolerance_seconds=_DURATION_TOLERANCE_SECONDS,
        )
    )

    video = probe.video
    checks.append(
        _check("output.video_stream", "pass" if video is not None else "fail", "video stream present" if video is not None else "video stream missing")
    )
    resolution_matches = video is not None and (
        (expected.width is None or video.width == expected.width)
        and (expected.height is None or video.height == expected.height)
    )
    checks.append(
        _check(
            "output.resolution",
            "pass" if resolution_matches else "fail",
            "output resolution matches expectation" if resolution_matches else "output resolution is missing or does not match expectation",
            actual_width=video.width if video else None,
            actual_height=video.height if video else None,
            expected_width=expected.width,
            expected_height=expected.height,
        )
    )
    audio_matches = not expected.audio_required or probe.audio is not None
    checks.append(
        _check(
            "output.audio_stream",
            "pass" if audio_matches else "fail",
            "audio stream requirement is satisfied" if audio_matches else "required audio stream missing",
        )
    )

    for name, detected in (("output.black_frame_start", expected.black_frame_at_start), ("output.black_frame_end", expected.black_frame_at_end)):
        status: QAStatus = "fail" if detected and not expected.black_frames_allowed else "warn" if detected else "pass"
        checks.append(
            _check(name, status, "black frame detected" if detected else "no black frame detected")
        )
    peak = expected.audio_peak_dbfs
    peak_exceeds_warning = peak is not None and peak > _AUDIO_PEAK_WARNING_DBFS
    peak_exceeds_expectation = peak is not None and expected.maximum_audio_peak_dbfs is not None and peak > expected.maximum_audio_peak_dbfs
    checks.append(
        _check(
            "output.audio_peak",
            "fail" if peak_exceeds_expectation else "warn" if peak_exceeds_warning else "pass",
            "audio peak exceeds required limit" if peak_exceeds_expectation else "audio peak exceeds advisory limit" if peak_exceeds_warning else "audio peak is acceptable",
            peak_dbfs=peak,
        )
    )
    return checks
