"""Shared integration fixtures for real local media verification."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from scripts.make_fixture import make_fixture
from videoos.analysis.probe import probe_media
from videoos.analysis.runner import CommandRunner


@pytest.fixture
def synthetic_video(tmp_path: Path) -> Path:
    """Create a local H.264/AAC source with deterministic one-second silence bookends."""
    missing = [binary for binary in ("ffmpeg", "ffprobe") if shutil.which(binary) is None]
    if missing:
        pytest.skip(f"integration requires local binaries: {', '.join(missing)}")
    source = make_fixture(tmp_path / "synthetic-silence.mp4")
    probe = probe_media(source, CommandRunner())
    assert probe.duration == pytest.approx(4.0, abs=0.1)
    assert probe.video is not None
    assert probe.video.codec_name == "h264"
    assert (probe.video.width, probe.video.height) == (640, 360)
    assert probe.audio is not None
    assert probe.audio.codec_name == "aac"
    return source
