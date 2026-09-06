"""Bounded local content measurements; unavailable evidence stays unknown."""

import re
from pathlib import Path

from videoos.analysis.models import MediaProbe
from videoos.analysis.runner import CommandRunner
from videoos.core.errors import ExternalCommandError


def measure_content(path: Path, probe: MediaProbe, runner: CommandRunner) -> dict:
    measurements: dict = {}
    if probe.video is not None and probe.duration is not None:
        try:
            result = runner.run([
                "ffmpeg", "-nostdin", "-hide_banner", "-v", "info", "-i", str(path),
                "-vf", "blackdetect=d=0:pix_th=0.10:pic_th=0.98", "-an", "-f", "null", "-",
            ])
        except ExternalCommandError:
            pass
        else:
            intervals = [(float(start), float(end)) for start, end in re.findall(
                r"black_start:([\d.]+) black_end:([\d.]+)", result.stderr)]
            frame = 1 / (probe.video.frame_rate or 30)
            measurements["black_frame_at_start"] = any(start <= frame for start, _ in intervals)
            measurements["black_frame_at_end"] = any(end >= probe.duration - 2 * frame for _, end in intervals)
    if probe.audio is not None:
        try:
            result = runner.run([
                "ffmpeg", "-nostdin", "-hide_banner", "-v", "info", "-i", str(path),
                "-map", "0:a:0", "-af", "volumedetect", "-vn", "-f", "null", "-",
            ])
        except ExternalCommandError:
            pass
        else:
            peak = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB", result.stderr)
            if peak:
                measurements["audio_peak_dbfs"] = float(peak.group(1))
    return measurements
