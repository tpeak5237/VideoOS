import math
from dataclasses import dataclass


def finite_non_negative(value: float, field_name: str) -> float:
    """Return a timestamp-like value after finite and non-negative validation."""
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{field_name} must be finite")
    if numeric < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return numeric


def seconds(value: float, field_name: str) -> float:
    return finite_non_negative(value, field_name)


@dataclass(frozen=True)
class TimeRange:
    start: float
    end: float

    def __post_init__(self) -> None:
        start = finite_non_negative(self.start, "start")
        end = finite_non_negative(self.end, "end")
        if end < start:
            raise ValueError("end must be greater than or equal to start")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)

    def duration(self) -> float:
        return self.end - self.start

    def contains(self, value: float) -> bool:
        point = finite_non_negative(value, "value")
        return self.start <= point <= self.end
