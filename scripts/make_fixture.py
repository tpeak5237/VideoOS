"""Create tiny, deterministic local media fixtures without storing binaries in Git."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

_DIAGNOSTIC_STREAM_LIMIT = 512


def _diagnostic_excerpt(value: str | bytes | None) -> str:
    """Return a decoded, bounded subprocess stream excerpt for fixture failures."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return value[:_DIAGNOSTIC_STREAM_LIMIT]


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
        stdout_excerpt = _diagnostic_excerpt(error.stdout)
        stderr_excerpt = _diagnostic_excerpt(error.stderr)
        raise RuntimeError(
            "ffmpeg fixture generation failed "
            f"(stdout excerpt: {stdout_excerpt!r}; stderr excerpt: {stderr_excerpt!r})"
        ) from error
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("ffmpeg fixture generation did not create a non-empty output")
    return destination


def main(argv: list[str] | None = None) -> int:
    """Create a fixture at the output path supplied by the documented command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="destination MP4 path")
    arguments = parser.parse_args(argv)
    print(make_fixture(arguments.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
