from pathlib import Path

from videoos.analysis.scenes import detect_scenes


def test_scene_detector_adds_start_deduplicates_frame_times_and_ends_at_duration(tmp_path: Path):
    """Catches scene plans with missing edge boundaries or duplicate frame cuts."""
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fixture")

    class RecordingRunner:
        def run(self, args: list[str]) -> object:
            return type(
                "Result",
                (),
                {"stderr": "showinfo pts_time:0.000\nshowinfo pts_time:1.000\nshowinfo pts_time:1.001\n"},
            )()

    boundaries = detect_scenes(source, RecordingRunner(), duration=4.0)  # type: ignore[arg-type]

    assert [boundary.time for boundary in boundaries] == [0.0, 1.0, 4.0]
