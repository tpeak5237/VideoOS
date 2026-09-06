"""Basic local FFmpeg scene boundary detection."""

from __future__ import annotations

import re
from pathlib import Path

from .models import SceneBoundary
from .runner import CommandRunner

_PTS_TIME = re.compile(r"pts_time:(-?(?:\d+(?:\.\d*)?|\.\d+))")


def detect_scenes(
    path: Path,
    runner: CommandRunner,
    threshold: float = 0.35,
    *,
    duration: float | None = None,
    frame_interval: float = 1 / 24,
) -> list[SceneBoundary]:
    """Return deduplicated cut boundaries, including known media edges."""
    source = path.resolve(strict=True)
    result = runner.run(
        [
            "ffmpeg",
            "-v",
            "info",
            "-i",
            str(source),
            "-vf",
            f"select='gt(scene,{threshold})',showinfo",
            "-an",
            "-f",
            "null",
            "-",
        ]
    )
    times = [0.0]
    for match in _PTS_TIME.finditer(result.stderr):
        timestamp = float(match.group(1))
        if timestamp >= 0 and all(abs(timestamp - existing) > frame_interval for existing in times):
            times.append(timestamp)
    if duration is not None and duration >= 0:
        interior = [time for time in times if frame_interval < time < duration - frame_interval]
        times = [0.0, *interior]
        if duration > 0:
            times.append(duration)
    return [SceneBoundary(time=time) for time in sorted(times)]
