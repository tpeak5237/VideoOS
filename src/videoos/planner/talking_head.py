"""Pure, explainable talking-head edit planning without rendering dependencies."""

from __future__ import annotations

import math
from collections.abc import Sequence

from videoos.analysis.models import AnalysisArtifact, Transcript, TranscriptWord
from videoos.captions.segment import segment_transcript
from videoos.core.models import (
    AudioAdjustment,
    CaptionCue,
    DecisionParameters,
    Evidence,
    SourceSegment,
    TargetSpec,
    Timeline,
    Track,
    TransformSpec,
)
from videoos.core.time import TimeRange
from videoos.planner.timeline import source_to_timeline
from videoos.profiles.models import Profile

_CAPTION_MAX_DURATION_SECONDS = 2.0


def _duration(analysis: AnalysisArtifact) -> float:
    duration = analysis.probe.duration
    if duration is None or not math.isfinite(duration) or duration < 0:
        raise ValueError("analysis requires a finite non-negative media duration")
    return float(duration)


def _merge_silences(analysis: AnalysisArtifact, duration: float) -> list[TimeRange]:
    merged: list[TimeRange] = []
    for silence in sorted(analysis.silence_regions, key=lambda item: (item.start, item.end)):
        start, end = max(0.0, silence.start), min(duration, silence.end)
        if end < start:
            continue
        region = TimeRange(start=start, end=end)
        if merged and region.start <= merged[-1].end:
            merged[-1] = TimeRange(start=merged[-1].start, end=max(merged[-1].end, region.end))
        else:
            merged.append(region)
    return merged


def _silence_cuts(analysis: AnalysisArtifact, profile: Profile, duration: float) -> list[TimeRange]:
    if not profile.silence.remove or analysis.probe.audio is None:
        return []
    maximum_pause = profile.silence.max_pause_ms / 1000
    cuts: list[TimeRange] = []
    for silence in _merge_silences(analysis, duration):
        if silence.duration() <= maximum_pause:
            continue
        retained_start = silence.start + (silence.duration() - maximum_pause) / 2
        retained_end = retained_start + maximum_pause
        if retained_start > silence.start:
            cuts.append(TimeRange(start=silence.start, end=retained_start))
        if retained_end < silence.end:
            cuts.append(TimeRange(start=retained_end, end=silence.end))
    return cuts


def _keep_ranges(duration: float, cuts: Sequence[TimeRange]) -> list[TimeRange]:
    kept: list[TimeRange] = []
    cursor = 0.0
    for cut in cuts:
        if cursor < cut.start:
            kept.append(TimeRange(start=cursor, end=cut.start))
        cursor = max(cursor, cut.end)
    if cursor < duration:
        kept.append(TimeRange(start=cursor, end=duration))
    return kept


def _needs_center_crop(analysis: AnalysisArtifact, target: TargetSpec) -> bool:
    video = analysis.probe.video
    if video is None or video.width is None or video.height is None or video.height == 0:
        return False
    target_width, target_height = (int(part) for part in target.aspect_ratio.split(":", maxsplit=1))
    return not math.isclose(video.width / video.height, target_width / target_height, rel_tol=1e-9)


def _transform_for_segment(
    *,
    source_start: float,
    crop: bool,
    profile: Profile,
    scene_times: set[float],
    previous_zoom_start: float | None,
) -> tuple[TransformSpec | None, float | None]:
    zoom_scale: float | None = None
    can_zoom = profile.zoom.enabled and (
        previous_zoom_start is None
        or source_start - previous_zoom_start >= profile.zoom.min_interval_seconds
    )
    if can_zoom and (previous_zoom_start is None or source_start in scene_times):
        zoom_scale = profile.zoom.max_scale
    if not crop and zoom_scale is None:
        return None, previous_zoom_start
    return TransformSpec(crop_x=0.0 if crop else None, crop_y=0.0 if crop else None, zoom_scale=zoom_scale), (
        source_start if zoom_scale is not None else previous_zoom_start
    )


def _map_captions(
    transcript: Transcript | None,
    cuts: Sequence[TimeRange],
    profile: Profile,
) -> list[CaptionCue]:
    if transcript is None or not profile.captions.enabled:
        return []
    mapped_words: list[TranscriptWord] = []
    for word in transcript.words:
        start = source_to_timeline(word.start, cuts)
        end = source_to_timeline(word.end, cuts)
        if start is None or end is None or end < start:
            continue
        mapped_words.append(TranscriptWord(text=word.text, start=start, end=end))
    if not mapped_words:
        return []
    return segment_transcript(
        Transcript(provider=transcript.provider, words=mapped_words),
        max_words_per_line=profile.captions.max_words_per_line,
        max_duration=_CAPTION_MAX_DURATION_SECONDS,
    )


def plan_talking_head(analysis: AnalysisArtifact, profile: Profile, target: TargetSpec) -> Timeline:
    """Plan explainable silence trims, captions, and conservative output metadata."""
    duration = _duration(analysis)
    cuts = _silence_cuts(analysis, profile, duration)
    kept = _keep_ranges(duration, cuts)
    crop = _needs_center_crop(analysis, target)
    scene_times = {boundary.time for boundary in analysis.scene_boundaries}
    previous_zoom_start: float | None = None
    timeline_start = 0.0
    segments: list[SourceSegment] = []
    for keep in kept:
        transform, previous_zoom_start = _transform_for_segment(
            source_start=keep.start,
            crop=crop,
            profile=profile,
            scene_times=scene_times,
            previous_zoom_start=previous_zoom_start,
        )
        segments.append(
            SourceSegment(
                source_id=analysis.source_hash,
                source_start=keep.start,
                source_end=keep.end,
                timeline_start=timeline_start,
                role="primary",
                transform=transform,
                audio=AudioAdjustment(target_lufs=profile.audio.speech_target_lufs)
                if analysis.probe.audio is not None
                else None,
            )
        )
        timeline_start += keep.duration()
    removed = [
        SourceSegment(
            source_id=analysis.source_hash,
            source_start=cut.start,
            source_end=cut.end,
            evidence=Evidence(
                action="remove",
                reason="silence",
                confidence=0.99,
                start=cut.start,
                end=cut.end,
                parameters=DecisionParameters(silence_seconds=cut.duration()),
            ),
        )
        for cut in cuts
    ]
    timeline = Timeline(
        tracks=[Track(id="primary-video", kind="video", segments=segments)],
        captions=_map_captions(analysis.transcript, cuts, profile),
        removed=removed,
    )
    timeline.validate_against_sources({analysis.source_hash: duration})
    return timeline
