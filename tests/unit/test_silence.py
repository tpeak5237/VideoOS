from pathlib import Path

from videoos.analysis.silence import detect_silence, parse_silencedetect


def test_silencedetect_parser_pairs_start_and_end():
    """Catches treating an end marker as a region without its matching start."""
    stderr = """
[silencedetect @ 0x0] silence_start: 1.25
[silencedetect @ 0x0] silence_end: 2.75 | silence_duration: 1.5
"""

    assert parse_silencedetect(stderr)[0].start == 1.25
    assert parse_silencedetect(stderr)[0].end == 2.75


def test_unclosed_silence_is_not_invented():
    """Catches fabricating an end timestamp when FFmpeg reports only a start."""
    assert parse_silencedetect("silence_start: 3.0\n") == []


def test_detect_silence_uses_resolved_safe_arguments(tmp_path: Path):
    """Catches passing an unresolved media path or lossy silence filter options."""
    source = tmp_path / "clip with spaces.mp4"
    source.write_bytes(b"fixture")

    class RecordingRunner:
        args: list[str]

        def run(self, args: list[str]) -> object:
            self.args = args
            return type("Result", (), {"stderr": "silence_start: 1\nsilence_end: 2\n"})()

    runner = RecordingRunner()

    regions = detect_silence(source, runner, threshold_db=-30.0, min_duration=0.5)  # type: ignore[arg-type]

    assert [(region.start, region.end) for region in regions] == [(1.0, 2.0)]
    assert runner.args == [
        "ffmpeg",
        "-v",
        "info",
        "-i",
        str(source.resolve()),
        "-af",
        "silencedetect=n=-30.0dB:d=0.5",
        "-f",
        "null",
        "-",
    ]
