"""Versioned, dependency-free project and timeline data contracts."""

from __future__ import annotations

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


class TargetSpec(SchemaModel):
    aspect_ratio: str
    resolution: str

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

    @field_validator("id", "path")
    @classmethod
    def validate_nonempty_text(cls, value: str) -> str:
        if not value or "\x00" in value:
            raise ValueError("must be non-empty and must not contain NUL")
        return value


class AnalysisRef(SchemaModel):
    source_id: str
    path: str
    cache_key: str | None = None


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

    @field_validator("fade_in_seconds", "fade_out_seconds")
    @classmethod
    def validate_fades(cls, value: float | None, info: object) -> float | None:
        if value is None:
            return value
        return _timestamp(value, getattr(info, "field_name", "fade"))


class Evidence(SchemaModel):
    action: str
    reason: str
    confidence: float | None = None
    start: float
    end: float

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
    role: str | None = None
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
