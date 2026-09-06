"""Regressions for the final whole-branch review's data and render boundaries."""

from pathlib import Path

import pytest

from tests.unit.factories import make_analysis_fixture, make_project_and_timeline
from videoos.cli import _load_project, _write_project
from videoos.core.errors import UnsafePathError
from videoos.core.io import save_model_atomic
from videoos.core.models import TargetSpec, Track
from videoos.qa.checks import check_output, check_timeline
from videoos.qa.models import QAExpectation
from videoos.renderer.ffmpeg import FfmpegRenderer


@pytest.mark.parametrize("occupied", ["timeline.json", "project.json", "analysis"])
def test_initialization_preserves_existing_artifacts(tmp_path, occupied):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"source")
    artifact = make_analysis_fixture()
    destination = tmp_path / occupied
    if occupied == "analysis":
        destination.mkdir()
        destination = destination / f"{artifact.source_hash}.json"
    destination.write_bytes(b"user-owned")
    with pytest.raises((ValueError, OSError, UnsafePathError)):
        _write_project(source, artifact, project_dir=tmp_path,
                       target=TargetSpec(aspect_ratio="16:9", resolution="320x180"),
                       profile_name="generic", captions=False)
    assert destination.read_bytes() == b"user-owned"
    assert source.read_bytes() == b"source"


@pytest.mark.parametrize("layout", ["gap", "multiple", "audio", "overlap", "unknown"])
def test_renderer_rejects_unsupported_track_semantics(tmp_path, layout):
    project, timeline = make_project_and_timeline(tmp_path)
    segment = timeline.tracks[0].segments[0]
    if layout == "gap":
        segment.timeline_start = 1
    elif layout == "overlap":
        timeline.tracks[0].segments.append(segment.model_copy())
    else:
        timeline.tracks.append(Track(id="other", kind={"multiple": "video", "audio": "audio", "unknown": "effect"}[layout], segments=[segment]))
    with pytest.raises(ValueError):
        FfmpegRenderer().build_plan(timeline, project, output=tmp_path / "out.mp4")


@pytest.mark.parametrize("aspect,resolution", [("9:16", "320x180"), ("91:161", "91x161")])
def test_target_rejects_unrealizable_display_contract(aspect, resolution):
    with pytest.raises(ValueError):
        TargetSpec(aspect_ratio=aspect, resolution=resolution)


def test_qa_does_not_pass_unmeasured_content(tmp_path):
    output = tmp_path / "out.mp4"
    output.write_bytes(b"output")
    checks = check_output(output, QAExpectation(), make_analysis_fixture().probe)
    assert all(c.status == "warn" for c in checks if c.name in {
        "output.black_frame_start", "output.black_frame_end", "output.audio_peak"})


def test_timeline_only_source_bounds_are_unavailable(tmp_path):
    _, timeline = make_project_and_timeline(tmp_path)
    checks = check_timeline(timeline, None)
    assert next(c for c in checks if c.name == "timeline.source_bounds").status == "warn"


def test_relative_sources_use_manifest_directory(tmp_path, monkeypatch):
    project, timeline = make_project_and_timeline(tmp_path)
    project.sources[0].path = "sources/fixture.mp4"
    save_model_atomic(tmp_path / "project.json", project)
    save_model_atomic(tmp_path / "timeline.json", timeline)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    _, loaded, _ = _load_project(tmp_path / "project.json")
    assert Path(loaded.sources[0].path) == tmp_path / "sources/fixture.mp4"


@pytest.mark.parametrize("hardware,available,codec", [(False, False, "libx264"), (False, True, "libx264"), (True, False, "libx264"), (True, True, "h264_videotoolbox")])
def test_videotoolbox_requires_both_gates(tmp_path, hardware, available, codec):
    project, timeline = make_project_and_timeline(tmp_path)
    plan = FfmpegRenderer(hardware_encoding=hardware, capabilities={"h264_videotoolbox": available}).build_plan(timeline, project, output=tmp_path / "out.mp4")
    assert plan.video_codec == codec


@pytest.mark.parametrize("kind", ["parent", "symlink"])
def test_manifest_relative_source_cannot_escape_project(tmp_path, kind):
    project, timeline = make_project_and_timeline(tmp_path)
    root = tmp_path / "project"
    root.mkdir()
    if kind == "parent":
        project.sources[0].path = "../sources/fixture.mp4"
    else:
        (root / "link.mp4").symlink_to(Path(project.sources[0].path))
        project.sources[0].path = "link.mp4"
    save_model_atomic(root / "project.json", project)
    save_model_atomic(root / "timeline.json", timeline)
    with pytest.raises(UnsafePathError):
        _load_project(root / "project.json")


def test_display_qa_rejects_wrong_sample_aspect_ratio(tmp_path):
    from dataclasses import replace

    output = tmp_path / "out.mp4"
    output.write_bytes(b"output")
    probe = make_analysis_fixture().probe
    probe = replace(probe, video=replace(probe.video, sample_aspect_ratio=2, display_aspect_ratio=32/9))
    checks = check_output(output, QAExpectation(width=1920, height=1080, square_pixels_required=True), probe)
    assert next(c for c in checks if c.name == "output.display_ratio").status == "fail"


def test_exclusive_metadata_publication_preserves_racing_target(tmp_path):
    _, timeline = make_project_and_timeline(tmp_path)
    destination = tmp_path / "timeline.json"
    destination.write_bytes(b"racing user edit")
    with pytest.raises(FileExistsError):
        save_model_atomic(destination, timeline, exclusive=True)
    assert destination.read_bytes() == b"racing user edit"


def test_audio_adjustment_does_not_invent_absent_stream(tmp_path):
    from videoos.core.models import AudioAdjustment

    project, timeline = make_project_and_timeline(tmp_path)
    timeline.tracks[0].segments[0].audio = AudioAdjustment(gain_db=-20)
    plan = FfmpegRenderer().build_plan(timeline, project, output=tmp_path / "out.mp4")
    assert not plan.has_audio and "[0:a" not in plan.filter_graph
    assert any("without audio" in warning for warning in plan.warnings)


def test_measurement_tool_failure_preserves_unavailable_state(tmp_path):
    from videoos.core.errors import ExternalCommandError
    from videoos.qa.measurements import measure_content

    class UnavailableFilters:
        def run(self, args):
            raise ExternalCommandError("filter unavailable")

    assert measure_content(tmp_path / "output.mp4", make_analysis_fixture().probe, UnavailableFilters()) == {}
