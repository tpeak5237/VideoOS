"""ffprobe invocation and conservative metadata parsing."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from typing import Any

from .models import AudioStream, MediaProbe, VideoStream
from .runner import CommandRunner


def _optional_float(value: object) -> float | None:
    try:
        numeric = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _optional_int(value: object) -> int | None:
    numeric = _optional_float(value)
    if numeric is None or not numeric.is_integer():
        return None
    return int(numeric)


def _frame_rate(value: object) -> float | None:
    if not isinstance(value, str):
        return _optional_float(value)
    try:
        numeric = float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return None
    return numeric if math.isfinite(numeric) else None


def _rotation(stream: Mapping[str, object]) -> int | None:
    tags = stream.get("tags")
    if isinstance(tags, Mapping):
        rotation = _optional_int(tags.get("rotate"))
        if rotation is not None:
            return rotation
    side_data = stream.get("side_data_list")
    if isinstance(side_data, list):
        for entry in side_data:
            if isinstance(entry, Mapping):
                rotation = _optional_int(entry.get("rotation"))
                if rotation is not None:
                    return rotation
    return None


def parse_ffprobe_json(payload: Mapping[str, object]) -> MediaProbe:
    """Convert ffprobe JSON to typed metadata without guessing missing values."""
    format_data = payload.get("format")
    duration = _optional_float(format_data.get("duration")) if isinstance(format_data, Mapping) else None
    video: VideoStream | None = None
    audio: AudioStream | None = None
    streams = payload.get("streams")
    if not isinstance(streams, list):
        streams = []
    for stream in streams:
        if not isinstance(stream, Mapping):
            continue
        codec_type = stream.get("codec_type")
        if codec_type == "video" and video is None:
            codec_name = stream.get("codec_name")
            video = VideoStream(
                codec_name=codec_name if isinstance(codec_name, str) else None,
                width=_optional_int(stream.get("width")),
                height=_optional_int(stream.get("height")),
                frame_rate=_frame_rate(stream.get("r_frame_rate")),
                rotation=_rotation(stream),
            )
        elif codec_type == "audio" and audio is None:
            codec_name = stream.get("codec_name")
            audio = AudioStream(
                codec_name=codec_name if isinstance(codec_name, str) else None,
                sample_rate=_optional_int(stream.get("sample_rate")),
                channels=_optional_int(stream.get("channels")),
            )
    return MediaProbe(duration=duration, video=video, audio=audio)


def probe_media(path: Path, runner: CommandRunner) -> MediaProbe:
    """Probe an existing source file with ffprobe using its resolved path."""
    source = path.resolve(strict=True)
    result = runner.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(source),
        ]
    )
    payload: Any = json.loads(result.stdout)
    if not isinstance(payload, Mapping):
        raise TypeError("ffprobe returned a JSON value other than an object")
    return parse_ffprobe_json(payload)
