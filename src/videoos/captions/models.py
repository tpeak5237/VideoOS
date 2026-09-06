"""Caption rendering contracts."""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, field_validator


class CaptionStyle(BaseModel):
    """A deliberately small, portable ASS style definition."""

    model_config = ConfigDict(extra="forbid")

    font_name: str = "Arial"
    font_size: float = 48.0
    primary_colour: str = "&H00FFFFFF"
    outline_colour: str = "&H00000000"
    outline: float = 2.0
    shadow: float = 0.0
    alignment: int = 2
    margin_v: int = 48

    @field_validator("font_name")
    @classmethod
    def validate_font_name(cls, value: str) -> str:
        if not value or any(character in value for character in ",\r\n"):
            raise ValueError("font_name must be non-empty and cannot contain commas or line breaks")
        return value

    @field_validator("font_size", "outline", "shadow")
    @classmethod
    def validate_finite_non_negative(cls, value: float) -> float:
        numeric = float(value)
        if not math.isfinite(numeric) or numeric < 0:
            raise ValueError("style dimensions must be finite and non-negative")
        return numeric

    @field_validator("alignment")
    @classmethod
    def validate_alignment(cls, value: int) -> int:
        if value not in range(1, 10):
            raise ValueError("alignment must be between 1 and 9")
        return value

    @field_validator("margin_v")
    @classmethod
    def validate_margin_v(cls, value: int) -> int:
        if value < 0:
            raise ValueError("margin_v must be non-negative")
        return value
