from pathlib import Path

from videoos.analysis.probe import parse_ffprobe_json, probe_media


def test_probe_parser_extracts_video_and_audio():
    """Catches losing available stream metadata when parsing ffprobe output."""
    probe = parse_ffprobe_json(
        {
            "format": {"duration": "4.5"},
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 640,
                    "height": 360,
                    "r_frame_rate": "30000/1001",
                    "tags": {"rotate": "90"},
                },
                {
                    "index": 1,
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "48000",
                    "channels": 1,
                },
            ],
        }
    )

    assert probe.duration == 4.5
    assert probe.video is not None
    assert probe.video.width == 640
    assert probe.video.frame_rate == 30000 / 1001
    assert probe.video.rotation == 90
    assert probe.audio is not None
    assert probe.audio.channels == 1


def test_probe_parser_distinguishes_absent_audio_from_unknown_audio_fields():
    """Catches representing a present-but-incomplete audio stream as absent."""
    no_audio = parse_ffprobe_json({"format": {}, "streams": []})
    unknown_audio = parse_ffprobe_json(
        {"format": {}, "streams": [{"codec_type": "audio"}]}
    )

    assert no_audio.audio is None
    assert unknown_audio.audio is not None
    assert unknown_audio.audio.codec_name is None
    assert unknown_audio.audio.sample_rate is None
    assert unknown_audio.audio.channels is None


def test_probe_media_uses_resolved_path_and_required_ffprobe_arguments(tmp_path: Path):
    """Catches passing an unresolved user path or a lossy ffprobe command."""
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fixture")

    class RecordingRunner:
        args: list[str]

        def run(self, args: list[str]) -> object:
            self.args = args
            return type(
                "Result",
                (),
                {"stdout": '{"format": {"duration": "1"}, "streams": []}'},
            )()

    runner = RecordingRunner()

    probe = probe_media(source, runner)  # type: ignore[arg-type]

    assert probe.duration == 1
    assert runner.args == [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(source.resolve()),
    ]
