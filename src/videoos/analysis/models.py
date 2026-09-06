"""Typed metadata and stable artifacts produced by local media analysis."""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


@dataclass(frozen=True)
class VideoStream:
    codec_name: str | None
    width: int | None
    height: int | None
    frame_rate: float | None
    rotation: int | None
    sample_aspect_ratio: float | None = None
    display_aspect_ratio: float | None = None


@dataclass(frozen=True)
class AudioStream:
    codec_name: str | None
    sample_rate: int | None
    channels: int | None


@dataclass(frozen=True)
class MediaProbe:
    duration: float | None
    video: VideoStream | None
    audio: AudioStream | None


class AnalysisModel(BaseModel):
    """Strict JSON-safe analysis model base."""

    model_config = ConfigDict(extra="forbid")


def _finite_non_negative(value: float, field_name: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError(f"{field_name} must be finite and non-negative")
    return numeric


class SilenceRegion(AnalysisModel):
    start: float
    end: float
    reason: str = "silence"
    confidence: float = 0.99

    @field_validator("start", "end")
    @classmethod
    def validate_timestamp(cls, value: float, info: object) -> float:
        return _finite_non_negative(value, getattr(info, "field_name", "timestamp"))

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        numeric = _finite_non_negative(value, "confidence")
        if numeric > 1:
            raise ValueError("confidence must be at most 1")
        return numeric

    @model_validator(mode="after")
    def validate_range(self) -> SilenceRegion:
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        if self.reason != "silence":
            raise ValueError("reason must be silence")
        return self


class SceneBoundary(AnalysisModel):
    time: float

    @field_validator("time")
    @classmethod
    def validate_time(cls, value: float) -> float:
        return _finite_non_negative(value, "time")


class SpeechRegion(AnalysisModel):
    start: float
    end: float
    text: str

    @field_validator("start", "end")
    @classmethod
    def validate_timestamp(cls, value: float, info: object) -> float:
        return _finite_non_negative(value, getattr(info, "field_name", "timestamp"))

    @model_validator(mode="after")
    def validate_range(self) -> SpeechRegion:
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


class TranscriptWord(AnalysisModel):
    """A word recognized by a local speech provider with source-media timings."""

    text: str
    start: float
    end: float

    @field_validator("start", "end")
    @classmethod
    def validate_timestamp(cls, value: float, info: object) -> float:
        return _finite_non_negative(value, getattr(info, "field_name", "timestamp"))

    @model_validator(mode="after")
    def validate_range(self) -> TranscriptWord:
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


class Transcript(AnalysisModel):
    provider: str = "unknown"
    regions: list[SpeechRegion] = Field(default_factory=list)
    words: list[TranscriptWord] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_word_order(self) -> Transcript:
        """Reject descending word starts; same-start/overlapping words remain valid."""
        if any(current.start < previous.start for previous, current in pairwise(self.words)):
            raise ValueError("words must be ordered by nondecreasing start timestamp")
        return self


class CapabilityStatus(AnalysisModel):
    name: str
    available: bool
    reason: str | None = None
    warning: str | None = None


class AnalysisConfig(AnalysisModel):
    silence_threshold_db: float = -35.0
    minimum_silence_duration: float = 0.3
    scene_threshold: float = 0.35
    provider_fingerprint: str = "none"
    tool_fingerprint: str | None = None

    @field_validator("silence_threshold_db", "minimum_silence_duration", "scene_threshold")
    @classmethod
    def validate_finite(cls, value: float, info: object) -> float:
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError(f"{getattr(info, 'field_name', 'value')} must be finite")
        if getattr(info, "field_name", "") in {"minimum_silence_duration", "scene_threshold"} and numeric < 0:
            raise ValueError(f"{getattr(info, 'field_name', 'value')} must be non-negative")
        return numeric


class AnalysisArtifact(AnalysisModel):
    source_hash: str
    probe: MediaProbe
    analysis_fingerprint: str
    tool_fingerprint: str
    silence_regions: list[SilenceRegion] = Field(default_factory=list)
    scene_boundaries: list[SceneBoundary] = Field(default_factory=list)
    transcript: Transcript | None = None
    capabilities: list[CapabilityStatus] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("source_hash", "analysis_fingerprint", "tool_fingerprint")
    @classmethod
    def validate_digest(cls, value: str, info: object) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError(f"{getattr(info, 'field_name', 'digest')} must be a lowercase SHA-256 digest")
        return value
