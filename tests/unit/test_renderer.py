from pathlib import Path

import pytest

from tests.unit.factories import make_project_and_timeline
from videoos.core.errors import UnsafePathError
from videoos.core.models import (
    AudioAdjustment,
    CaptionCue,
    SourceSegment,
    Track,
    TransformSpec,
)
from videoos.renderer.ffmpeg import FfmpegRenderer, escape_subtitles_filter_path


def test_renderer_uses_argv_and_keeps_user_path_as_one_argument(tmp_path: Path):
    project, timeline = make_project_and_timeline(tmp_path)
    output = tmp_path / "render with spaces.mp4"

    plan = FfmpegRenderer().build_plan(timeline, project, output=output)

    assert plan.argv[0] == "ffmpeg"
    assert str(project.sources[0].path) in plan.argv
    assert all(";" not in argument for argument in plan.argv)
    assert "trim=start=0:end=4" in plan.filter_graph
    assert "scale=1920:1080:force_original_aspect_ratio=increase" in plan.filter_graph
    assert "crop=1920:1080" in plan.filter_graph
    assert "[aout]" not in plan.argv


def test_subtitle_filter_path_escapes_colon_and_quote(tmp_path: Path):
    path = tmp_path / "a:b'c.srt"

    escaped = escape_subtitles_filter_path(path)

    assert "\\:" in escaped
    assert "\\'" in escaped


def test_dry_run_does_not_create_output(tmp_path: Path):
    project, timeline = make_project_and_timeline(tmp_path)
    output = tmp_path / "out.mp4"
    plan = FfmpegRenderer().build_plan(timeline, project, output=output)

    result = FfmpegRenderer().render(plan, dry_run=True)

    assert result.dry_run is True
    assert result.output is None
    assert not output.exists()


def test_audio_graph_concatenates_trimmed_segments_and_burns_controlled_captions(tmp_path: Path):
    project, timeline = make_project_and_timeline(tmp_path)
    source = timeline.tracks[0].segments[0]
    timeline = timeline.model_copy(
        update={
            "tracks": [
                Track(
                    id="video",
                    kind="video",
                    segments=[
                        source.model_copy(
                            update={
                                "transform": TransformSpec(crop_x=10, crop_y=20, zoom_scale=1.05),
                                "audio": AudioAdjustment(target_lufs=-16),
                            }
                        ),
                        SourceSegment(
                            source_id="main",
                            source_start=4,
                            source_end=6,
                            timeline_start=4,
                            audio=AudioAdjustment(target_lufs=-16),
                        ),
                    ],
                )
            ],
            "captions": [CaptionCue(start=0, end=1, text="Hello")],
        }
    )
    captions = tmp_path / "captions:final's.srt"
    captions.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    plan = FfmpegRenderer().build_plan(
        timeline, project, output=tmp_path / "out.mp4", caption_file=captions
    )

    assert "atrim=start=0:end=4" in plan.filter_graph
    assert "concat=n=2:v=1:a=1" in plan.filter_graph
    assert "zoompan=z='min(1.05,zoom+0.0)'" in plan.filter_graph
    assert "subtitles=filename='" in plan.filter_graph
    assert "\\:" in plan.filter_graph and "\\'" in plan.filter_graph
    assert "[aout]" in plan.argv
    assert "-af" in plan.argv
    assert plan.argv[plan.argv.index("-c:v") + 1] == "libx264"


def test_renderer_rejects_output_path_that_is_a_source(tmp_path: Path):
    project, timeline = make_project_and_timeline(tmp_path)

    with pytest.raises(UnsafePathError, match="source"):
        FfmpegRenderer().build_plan(timeline, project, output=Path(project.sources[0].path))


def test_renderer_publishes_nonempty_managed_stage_after_success(tmp_path: Path):
    project, timeline = make_project_and_timeline(tmp_path)
    output = tmp_path / "out.mp4"
    plan = FfmpegRenderer().build_plan(timeline, project, output=output)

    class WritingRunner:
        def run(self, args: list[str], *, timeout: float | None = None):
            Path(args[-1]).write_bytes(b"rendered")
            return type("Result", (), {"stdout": "ok", "stderr": ""})()

    result = FfmpegRenderer(runner=WritingRunner()).render(plan)

    assert result.output == output
    assert result.dry_run is False
    assert output.read_bytes() == b"rendered"
    assert not list(tmp_path.glob(".out.mp4.*.part"))
