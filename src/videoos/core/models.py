"""Versioned, dependency-free project and timeline data contracts."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .time import finite_non_negative


class SchemaModel(BaseModel):
    """Base model that rejects unrecognised structured schema fields."""

    model_config = ConfigDict(extra="forbid")


def _timestamp(value: float, field_name: str) -> float:
    return finite_non_negative(value, field_name)


def _finite_in_range(value: float, field_name: str, minimum: float, maximum: float) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{field_name} must be finite")
    if not minimum <= numeric <= maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")
    return numeric


def _sha256(value: str, field_name: str) -> str:
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
    return value


class TargetSpec(SchemaModel):
    aspect_ratio: str
    resolution: str

    @model_validator(mode="after")
    def validate_display_dimensions(self) -> TargetSpec:
        numerator, denominator = map(int, self.aspect_ratio.split(":"))
        if self.width % 2 or self.height % 2:
            raise ValueError("H.264/yuv420p resolution must have even dimensions")
        if self.width * denominator != self.height * numerator:
            raise ValueError("resolution must match aspect_ratio")
        return self

    @property
    def width(self) -> int:
        return int(self.resolution.split("x", maxsplit=1)[0])

    @property
    def height(self) -> int:
        return int(self.resolution.split("x", maxsplit=1)[1])

    @field_validator("aspect_ratio")
    @classmethod
    def validate_aspect_ratio(cls, value: str) -> str:
        match = re.fullmatch(r"([1-9]\d*):([1-9]\d*)", value)
        if match is None:
            raise ValueError("aspect_ratio must be a positive W:H ratio")
        return value

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, value: str) -> str:
        if re.fullmatch(r"[1-9]\d*x[1-9]\d*", value) is None:
            raise ValueError("resolution must be a positive WIDTHxHEIGHT value")
        return value


class SourceRef(SchemaModel):
    id: str
    path: str
    has_audio: bool | None = None

    @field_validator("id", "path")
    @classmethod
    def validate_nonempty_text(cls, value: str) -> str:
        if not value or "\x00" in value:
            raise ValueError("must be non-empty and must not contain NUL")
        return value


class AnalysisRef(SchemaModel):
    source_id: str
    path: str
    source_sha256: str | None = None
    analysis_config_fingerprint: str | None = None
    tool_fingerprint: str | None = None
    cache_key: str | None = Field(default=None, max_length=256)

    @field_validator("source_sha256", "analysis_config_fingerprint", "tool_fingerprint")
    @classmethod
    def validate_fingerprint(cls, value: str | None, info: object) -> str | None:
        if value is None:
            return value
        return _sha256(value, getattr(info, "field_name", "fingerprint"))

    @field_validator("cache_key")
    @classmethod
    def validate_legacy_cache_key(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("cache_key must be non-empty when present")
        return value

    @model_validator(mode="after")
    def validate_identity(self) -> AnalysisRef:
        modern_fields = (
            self.source_sha256,
            self.analysis_config_fingerprint,
            self.tool_fingerprint,
        )
        if self.cache_key is not None:
            if any(field is not None for field in modern_fields):
                raise ValueError("legacy cache_key cannot be combined with modern cache identity")
            return self
        if not all(field is not None for field in modern_fields):
            raise ValueError("modern cache identity requires all validated fingerprints")
        return self

    @property
    def is_cache_reusable(self) -> bool:
        return self.cache_key is None and all(
            field is not None
            for field in (
                self.source_sha256,
                self.analysis_config_fingerprint,
                self.tool_fingerprint,
            )
        )

    @property
    def cache_identity(self) -> str | None:
        if not self.is_cache_reusable:
            return None
        assert self.source_sha256 is not None
        assert self.analysis_config_fingerprint is not None
        assert self.tool_fingerprint is not None
        identity = f"{self.source_sha256}\0{self.analysis_config_fingerprint}\0{self.tool_fingerprint}"
        return hashlib.sha256(identity.encode("ascii")).hexdigest()


class ProjectManifest(SchemaModel):
    version: Literal["1"]
    project_id: str
    name: str
    sources: list[SourceRef] = Field(min_length=1)
    target: TargetSpec
    analysis: list[AnalysisRef] = Field(default_factory=list)

    @field_validator("project_id", "name")
    @classmethod
    def validate_identity(cls, value: str) -> str:
        if not value or "\x00" in value:
            raise ValueError("must be non-empty and must not contain NUL")
        return value

    @model_validator(mode="after")
    def require_unique_source_ids(self) -> ProjectManifest:
        source_ids = [source.id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source ids must be unique")
        unknown_analysis_sources = {
            reference.source_id for reference in self.analysis if reference.source_id not in source_ids
        }
        if unknown_analysis_sources:
            raise ValueError("analysis reference has an unknown source_id")
        return self


class TransformSpec(SchemaModel):
    crop_x: float | None = None
    crop_y: float | None = None
    zoom_scale: float | None = None

    @field_validator("crop_x", "crop_y")
    @classmethod
    def validate_crop_offset(cls, value: float | None, info: object) -> float | None:
        if value is None:
            return value
        return _timestamp(value, getattr(info, "field_name", "crop_offset"))

    @field_validator("zoom_scale")
    @classmethod
    def validate_zoom_scale(cls, value: float | None) -> float | None:
        if value is None:
            return value
        numeric = _timestamp(value, "zoom_scale")
        if numeric < 1:
            raise ValueError("zoom_scale must be at least 1")
        return numeric


class AudioAdjustment(SchemaModel):
    gain_db: float | None = None
    target_lufs: float | None = None
    fade_in_seconds: float | None = None
    fade_out_seconds: float | None = None

    @field_validator("gain_db")
    @classmethod
    def validate_gain_db(cls, value: float | None) -> float | None:
        if value is None:
            return value
        return _finite_in_range(value, "gain_db", -60, 24)

    @field_validator("target_lufs")
    @classmethod
    def validate_target_lufs(cls, value: float | None) -> float | None:
        if value is None:
            return value
        return _finite_in_range(value, "target_lufs", -70, -5)

    @field_validator("fade_in_seconds", "fade_out_seconds")
    @classmethod
    def validate_fades(cls, value: float | None, info: object) -> float | None:
        if value is None:
            return value
        return _timestamp(value, getattr(info, "field_name", "fade"))


class DecisionParameters(SchemaModel):
    silence_seconds: float | None = None
    scene_index: int | None = Field(default=None, ge=0, le=1_000_000)

    @field_validator("silence_seconds")
    @classmethod
    def validate_silence_seconds(cls, value: float | None) -> float | None:
        if value is None:
            return value
        return _finite_in_range(value, "silence_seconds", 0, 600)


EvidenceAction = Literal[
    "keep", "remove", "trim", "reframe", "zoom", "normalize_audio", "caption"
]
EvidenceReason = Literal[
    "manual", "silence", "scene_boundary", "speech", "framing", "loudness", "transcript", "heuristic_window"
]
SegmentRole = Literal["primary", "b_roll", "cutaway", "overlay", "voiceover"]


class Evidence(SchemaModel):
    action: EvidenceAction
    reason: EvidenceReason
    confidence: float | None = None
    start: float
    end: float
    parameters: DecisionParameters | None = None

    @field_validator("start", "end")
    @classmethod
    def validate_timestamps(cls, value: float, info: object) -> float:
        return _timestamp(value, getattr(info, "field_name", "timestamp"))

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float | None) -> float | None:
        if value is None:
            return value
        numeric = _timestamp(value, "confidence")
        if numeric > 1:
            raise ValueError("confidence must be at most 1")
        return numeric

    @model_validator(mode="after")
    def validate_range(self) -> Evidence:
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


class SourceSegment(SchemaModel):
    source_id: str
    source_start: float = 0
    source_end: float
    timeline_start: float = 0
    role: SegmentRole | None = None
    transform: TransformSpec | None = None
    audio: AudioAdjustment | None = None
    evidence: Evidence | None = None

    @field_validator("source_start", "source_end", "timeline_start")
    @classmethod
    def validate_timestamps(cls, value: float, info: object) -> float:
        return _timestamp(value, getattr(info, "field_name", "timestamp"))

    @model_validator(mode="after")
    def validate_source_range(self) -> SourceSegment:
        if self.source_end < self.source_start:
            raise ValueError("source_end must be greater than or equal to source_start")
        return self

    @property
    def duration_seconds(self) -> float:
        return self.source_end - self.source_start

    @property
    def timeline_end(self) -> float:
        return self.timeline_start + self.duration_seconds


class CaptionCue(SchemaModel):
    start: float
    end: float
    text: str

    @field_validator("start", "end")
    @classmethod
    def validate_timestamps(cls, value: float, info: object) -> float:
        return _timestamp(value, getattr(info, "field_name", "timestamp"))

    @model_validator(mode="after")
    def validate_range(self) -> CaptionCue:
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


class Track(SchemaModel):
    id: str
    kind: str
    segments: list[SourceSegment] = Field(default_factory=list)


class Timeline(SchemaModel):
    version: Literal["1"] = "1"
    tracks: list[Track] = Field(default_factory=list)
    captions: list[CaptionCue] = Field(default_factory=list)
    removed: list[SourceSegment] = Field(default_factory=list)

    def duration_seconds(self) -> float:
        return max((segment.timeline_end for track in self.tracks for segment in track.segments), default=0.0)

    def validate_against_sources(self, source_durations: Mapping[str, float]) -> None:
        durations = {
            source_id: _timestamp(duration, f"source duration for {source_id}")
            for source_id, duration in source_durations.items()
        }
        for track in self.tracks:
            previous_end = 0.0
            for segment in sorted(track.segments, key=lambda item: item.timeline_start):
                source_duration = durations.get(segment.source_id)
                if source_duration is None:
                    raise ValueError(f"unknown source: {segment.source_id}")
                if segment.source_end > source_duration:
                    raise ValueError(f"source range exceeds duration: {segment.source_id}")
                if segment.timeline_start < previous_end:
                    raise ValueError(f"track {track.id} contains overlap")
                previous_end = segment.timeline_end

        timeline_duration = self.duration_seconds()
        for cue in self.captions:
            if cue.end > timeline_duration:
                raise ValueError("caption range exceeds timeline duration")
