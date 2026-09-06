"""Local FFmpeg silence detection with conservative parsing."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from .models import SilenceRegion
from .runner import CommandRunner

_START = re.compile(r"(?:^|\s)silence_start:\s*(-?(?:\d+(?:\.\d*)?|\.\d+))\s*$", re.MULTILINE)
_END = re.compile(r"(?:^|\s)silence_end:\s*(-?(?:\d+(?:\.\d*)?|\.\d+))(?=\s|$)", re.MULTILINE)


def parse_silencedetect(stderr: str) -> list[SilenceRegion]:
    """Return only FFmpeg silence ranges that have both finite endpoints."""
    regions: list[SilenceRegion] = []
    start: float | None = None
    for line in stderr.splitlines():
        start_match = _START.search(line)
        if start_match is not None:
            candidate = float(start_match.group(1))
            start = candidate if candidate >= 0 else None
            continue
        end_match = _END.search(line)
        if end_match is None or start is None:
            continue
        end = float(end_match.group(1))
        if end >= start:
            regions.append(SilenceRegion(start=start, end=end))
        start = None
    return regions


def _has_unclosed_silence(stderr: str) -> bool:
    start: float | None = None
    for line in stderr.splitlines():
        start_match = _START.search(line)
        if start_match is not None:
            candidate = float(start_match.group(1))
            start = candidate if candidate >= 0 else None
            continue
        if _END.search(line) is not None:
            start = None
    return start is not None


def detect_silence(
    path: Path,
    runner: CommandRunner,
    *,
    threshold_db: float = -35.0,
    min_duration: float = 0.3,
    on_unclosed: Callable[[], None] | None = None,
) -> list[SilenceRegion]:
    """Run FFmpeg locally and return fully observed silence regions only."""
    source = path.resolve(strict=True)
    result = runner.run(
        [
            "ffmpeg",
            "-v",
            "info",
            "-i",
            str(source),
            "-af",
            f"silencedetect=n={threshold_db}dB:d={min_duration}",
            "-f",
            "null",
            "-",
        ]
    )
    if on_unclosed is not None and _has_unclosed_silence(result.stderr):
        on_unclosed()
    return parse_silencedetect(result.stderr)
