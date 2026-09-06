"""Strict, JSON-safe data contracts for deterministic QA results."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

QAStatus = Literal["pass", "warn", "fail"]


class QAModel(BaseModel):
    """Base model that rejects unrecognised QA fields."""

    model_config = ConfigDict(extra="forbid")


def _finite(value: float, field_name: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{field_name} must be finite")
    return numeric


class QACheck(QAModel):
    name: str = Field(min_length=1)
    status: QAStatus
    message: str = Field(min_length=1)
    evidence: dict[str, str | int | float | bool | None] | None = None

    @field_validator("evidence")
    @classmethod
    def validate_evidence(cls, value: dict[str, str | int | float | bool | None] | None):
        if value is None:
            return value
        for key, item in value.items():
            if isinstance(item, float):
                value[key] = _finite(item, f"evidence {key}")
        return value


class QAExpectation(QAModel):
    duration: float | None = None
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    audio_required: bool = False
    black_frame_at_start: bool = False
    black_frame_at_end: bool = False
    black_frames_allowed: bool = True
    audio_peak_dbfs: float | None = None
    maximum_audio_peak_dbfs: float | None = None

    @field_validator("duration", "audio_peak_dbfs", "maximum_audio_peak_dbfs")
    @classmethod
    def validate_finite_measurement(cls, value: float | None, info: object) -> float | None:
        if value is None:
            return value
        return _finite(value, getattr(info, "field_name", "measurement"))

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("duration must be non-negative")
        return value


class QAReport(QAModel):
    passed: bool
    duration: float | None = None
    resolution: str | None = None
    warnings: list[str] = Field(default_factory=list)
    checks: list[QACheck] = Field(default_factory=list)

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, value: float | None) -> float | None:
        if value is None:
            return value
        return _finite(value, "duration")

    @model_validator(mode="after")
    def derive_passed_from_invariants(self) -> QAReport:
        if any(check.status == "fail" for check in self.checks):
            self.passed = False
        return self
