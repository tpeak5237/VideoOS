"""Create tiny, deterministic local media fixtures without storing binaries in Git."""

from __future__ import annotations

import subprocess
from pathlib import Path


def make_fixture(output: Path) -> Path:
    """Create a four-second 640x360 H.264/AAC MP4 with one-second silent bookends."""
    requested = Path(output).expanduser()
    requested.parent.mkdir(parents=True, exist_ok=True)
    destination = requested.parent.resolve(strict=True) / requested.name
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=steelblue:s=640x360:r=30:d=4",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=48000:cl=stereo:d=1",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=48000:duration=2",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=48000:cl=stereo:d=1",
        "-filter_complex",
        "[1:a][2:a][3:a]concat=n=3:v=0:a=1[aout]",
        "-map",
        "0:v:0",
        "-map",
        "[aout]",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        "-shortest",
        str(destination),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, shell=False)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"ffmpeg fixture generation failed: {error.stderr[:512]}") from error
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("ffmpeg fixture generation did not create a non-empty output")
    return destination
