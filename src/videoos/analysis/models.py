"""Typed metadata produced by local media probing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VideoStream:
    codec_name: str | None
    width: int | None
    height: int | None
    frame_rate: float | None
    rotation: int | None


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
