"""Cache-backed orchestration for local, non-destructive media analysis."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from videoos.core.errors import ExternalCommandError
from videoos.core.io import load_model, save_model_atomic

from .cache import AnalysisCache, sha256_file
from .models import (
    AnalysisArtifact,
    AnalysisConfig,
    CapabilityStatus,
    SceneBoundary,
    SilenceRegion,
    Transcript,
)
from .probe import probe_media
from .runner import CommandRunner
from .scenes import detect_scenes
from .silence import detect_silence


class Transcriber(Protocol):
    """Optional caller-owned transcription boundary; the service never uploads media."""

    def transcribe(self, path: Path) -> Transcript: ...


def _digest(value: Mapping[str, object]) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _known_duration(duration: float | None) -> float | None:
    if duration is None or not math.isfinite(duration) or duration < 0:
        return None
    return duration


def _merge_silences(regions: list[SilenceRegion], duration: float | None) -> list[SilenceRegion]:
    merged: list[SilenceRegion] = []
    for region in sorted(regions, key=lambda item: (item.start, item.end)):
        start = region.start
        end = region.end if duration is None else min(region.end, duration)
        if end < start:
            continue
        if merged and start <= merged[-1].end:
            merged[-1] = SilenceRegion(start=merged[-1].start, end=max(merged[-1].end, end))
        else:
            merged.append(SilenceRegion(start=start, end=end))
    return merged


def _fallback_scenes(duration: float | None) -> list[SceneBoundary]:
    if duration is None or duration == 0:
        return [SceneBoundary(time=0)]
    return [SceneBoundary(time=0), SceneBoundary(time=duration)]


class AnalysisService:
    """Coordinate local media analyzers, preserving cache and source boundaries."""

    def __init__(self, *, cache_dir: Path, runner: CommandRunner | None = None) -> None:
        self.cache = AnalysisCache(cache_dir)
        self.runner = runner or CommandRunner()

    def analyze(
        self,
        path: Path,
        *,
        config: AnalysisConfig,
        transcriber: Transcriber | None = None,
    ) -> AnalysisArtifact:
        """Analyze a strictly resolved local source, reusing its stable artifact when present."""
        source = path.resolve(strict=True)
        config_payload = config.model_dump(mode="json", exclude={"tool_fingerprint"})
        tool_payload = {"ffmpeg": config.tool_fingerprint}
        source_hash = sha256_file(source)
        analysis_fingerprint = _digest(config_payload)
        tool_fingerprint = _digest(tool_payload)
        artifact_path = self.cache.artifact_path(source_hash, analysis_fingerprint, tool_fingerprint)

        if artifact_path.is_file():
            cached = load_model(artifact_path, AnalysisArtifact)
            if (
                cached.source_hash == source_hash
                and cached.analysis_fingerprint == analysis_fingerprint
                and cached.tool_fingerprint == tool_fingerprint
            ):
                return cached

        probe = probe_media(source, self.runner)
        duration = _known_duration(probe.duration)
        warnings: list[str] = []
        capabilities: list[CapabilityStatus] = []

        silence_regions: list[SilenceRegion] = []
        if probe.audio is None:
            capabilities.append(CapabilityStatus(name="silence", available=False, warning="audio stream absent"))
        else:
            saw_unclosed_silence = False

            def record_unclosed_silence() -> None:
                nonlocal saw_unclosed_silence
                saw_unclosed_silence = True

            try:
                silence_regions = _merge_silences(
                    detect_silence(
                        source,
                        self.runner,
                        threshold_db=config.silence_threshold_db,
                        min_duration=config.minimum_silence_duration,
                        on_unclosed=record_unclosed_silence,
                    ),
                    duration,
                )
                capabilities.append(CapabilityStatus(name="silence", available=True))
                if saw_unclosed_silence:
                    warnings.append("ignored unclosed silence interval")
            except ExternalCommandError:
                capabilities.append(
                    CapabilityStatus(name="silence", available=False, warning="local silence detection unavailable")
                )
                warnings.append("local silence detection unavailable")

        try:
            scene_boundaries = detect_scenes(
                source, self.runner, config.scene_threshold, duration=duration
            )
            capabilities.append(CapabilityStatus(name="scenes", available=True))
        except ExternalCommandError:
            scene_boundaries = _fallback_scenes(duration)
            capabilities.append(
                CapabilityStatus(name="scenes", available=False, warning="local scene detection unavailable")
            )
            warnings.append("local scene detection unavailable")

        transcript: Transcript | None = None
        if transcriber is None:
            capabilities.append(CapabilityStatus(name="transcription", available=False, warning="not configured"))
        else:
            try:
                transcript = transcriber.transcribe(source)
                transcript = transcript.model_copy(
                    update={"regions": sorted(transcript.regions, key=lambda region: (region.start, region.end))}
                )
                capabilities.append(CapabilityStatus(name="transcription", available=True))
            except Exception:  # noqa: BLE001 - optional caller-owned providers must not block local analysis.
                capabilities.append(
                    CapabilityStatus(name="transcription", available=False, warning="transcription unavailable")
                )
                warnings.append("transcription unavailable")

        artifact = AnalysisArtifact(
            source_hash=source_hash,
            probe=probe,
            analysis_fingerprint=analysis_fingerprint,
            tool_fingerprint=tool_fingerprint,
            silence_regions=silence_regions,
            scene_boundaries=sorted(scene_boundaries, key=lambda item: item.time),
            transcript=transcript,
            capabilities=sorted(capabilities, key=lambda item: item.name),
            warnings=sorted(set(warnings)),
        )
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        save_model_atomic(artifact_path, artifact)
        return artifact
