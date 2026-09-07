"""Strict, portable policy contracts for deterministic edit planning."""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProfileModel(BaseModel):
    """Reject unknown policy keys so configuration mistakes remain visible."""

    model_config = ConfigDict(extra="forbid")


def _finite(value: float, field_name: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{field_name} must be finite")
    return numeric


class SilencePolicy(ProfileModel):
    remove: bool
    max_pause_ms: int = Field(ge=0, le=600_000)


class CaptionPolicy(ProfileModel):
    enabled: bool
    max_words_per_line: int = Field(ge=1, le=20)


class ReframePolicy(ProfileModel):
    subject_tracking: bool


class ZoomPolicy(ProfileModel):
    enabled: bool
    min_interval_seconds: float
    max_scale: float

    @field_validator("min_interval_seconds")
    @classmethod
    def validate_min_interval(cls, value: float) -> float:
        numeric = _finite(value, "min_interval_seconds")
        if numeric < 0:
            raise ValueError("min_interval_seconds must be non-negative")
        return numeric

    @field_validator("max_scale")
    @classmethod
    def validate_max_scale(cls, value: float) -> float:
        numeric = _finite(value, "max_scale")
        if numeric < 1 or numeric > 2:
            raise ValueError("max_scale must be between 1 and 2")
        return numeric


class AudioPolicy(ProfileModel):
    speech_target_lufs: float
    music_under_speech_lufs: float

    @field_validator("speech_target_lufs", "music_under_speech_lufs")
    @classmethod
    def validate_lufs(cls, value: float, info: object) -> float:
        field_name = getattr(info, "field_name", "lufs")
        numeric = _finite(value, field_name)
        if not -70 <= numeric <= 0:
            raise ValueError(f"{field_name} must be between -70 and 0")
        return numeric


class Profile(ProfileModel):
    name: str
    silence: SilencePolicy
    captions: CaptionPolicy
    reframe: ReframePolicy
    zoom: ZoomPolicy
    audio: AudioPolicy
    provenance: str

    @field_validator("name", "provenance")
    @classmethod
    def validate_text(cls, value: str, info: object) -> str:
        if not value or "\x00" in value:
            raise ValueError(f"{getattr(info, 'field_name', 'value')} must be non-empty and contain no NUL")
        return value
