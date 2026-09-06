from pathlib import Path

import pytest
from typer.testing import CliRunner

from videoos.analysis.models import MediaProbe, VideoStream
from videoos.cli import _qa_report, app
from videoos.core.io import load_model, save_model_atomic
from videoos.core.models import (
    ProjectManifest,
    SourceSegment,
    TargetSpec,
    Timeline,
    Track,
)

runner = CliRunner()


def test_analyze_missing_input_is_nonzero(tmp_path):
    """Dropping input-path validation must not turn a missing source into a successful analysis."""
    result = runner.invoke(app, ["analyze", str(tmp_path / "missing.mp4")])

    assert result.exit_code != 0
    assert "not found" in result.stdout.lower() or "not found" in result.stderr.lower()


def test_render_dry_run_does_not_reanalyze(project_fixture, monkeypatch):
    """Changing render to re-run analysis must fail: it only consumes persisted structured files."""
    calls = []
    monkeypatch.setattr("videoos.cli.AnalysisService.analyze", lambda *args, **kwargs: calls.append(True))

    result = runner.invoke(app, ["render", str(project_fixture / "project.json"), "--dry-run"])

    assert result.exit_code == 0
    assert calls == []


def test_render_dry_run_allows_an_existing_destination_without_mutating_it(project_fixture):
    """Dry runs plan an occupied output but must not replace the published media."""
    manifest = load_model(project_fixture / "project.json", ProjectManifest)
    output = project_fixture / "renders" / f"{Path(manifest.name).stem}.mp4"
    output.parent.mkdir()
    output.write_bytes(b"published-output")

    result = runner.invoke(app, ["render", str(project_fixture / "project.json"), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert output.read_bytes() == b"published-output"


def test_render_dry_run_emits_a_structured_plan(project_fixture):
    """Dry-run output must expose its argv-array and operations for inspection."""
    result = runner.invoke(app, ["render", str(project_fixture / "project.json"), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "plan" in result.output
    assert '"argv"' in result.output
    assert '"operations"' in result.output


def test_render_rejects_overlapping_source_overrun_before_planning(project_fixture, monkeypatch):
    """Dropping semantic validation must not render source overrun or overlapping segments."""
    timeline_path = project_fixture / "timeline.json"
    timeline = load_model(timeline_path, Timeline)
    source_id = timeline.tracks[0].segments[0].source_id
    invalid_timeline = timeline.model_copy(
        update={
            "tracks": [
                Track(
                    id="video",
                    kind="video",
                    segments=[
                        SourceSegment(source_id=source_id, source_start=0, source_end=4, timeline_start=0),
                        SourceSegment(source_id=source_id, source_start=1, source_end=8, timeline_start=1),
                    ],
                )
            ]
        }
    )
    save_model_atomic(timeline_path, invalid_timeline)
    calls = []
    monkeypatch.setattr("videoos.cli.AnalysisService.analyze", lambda *args, **kwargs: calls.append(True))

    result = runner.invoke(app, ["render", str(project_fixture / "project.json"), "--dry-run"])

    assert result.exit_code != 0
    assert "source range exceeds duration" in result.stderr.lower()
    assert calls == []


def test_qa_missing_output_is_nonzero(tmp_path):
    """Dropping output-path validation must not report QA success for absent media."""
    result = runner.invoke(app, ["qa", str(tmp_path / "missing.mp4"), "--json"])

    assert result.exit_code != 0


def test_qa_reports_failed_invariants_before_nonzero_exit(tmp_path, monkeypatch):
    """Replacing a failed QA report with a generic error must not hide its evidence."""
    output = tmp_path / "out.mp4"
    output.write_bytes(b"fixture")
    monkeypatch.setattr("videoos.cli.probe_media", lambda *args: MediaProbe(duration=1, video=None, audio=None))
    monkeypatch.setattr("videoos.cli.shutil.which", lambda _: "/usr/bin/ffprobe")

    result = runner.invoke(app, ["qa", str(output), "--json"])

    assert result.exit_code != 0
    assert '"passed":false' in result.stdout
    assert '"output.video_stream"' in result.stdout


def test_post_render_qa_checks_the_requested_target_resolution(tmp_path, monkeypatch):
    """Dropping target expectations must not let a wrong-size render pass QA."""
    output = tmp_path / "out.mp4"
    output.write_bytes(b"fixture")
    monkeypatch.setattr(
        "videoos.cli.probe_media",
        lambda *args: MediaProbe(
            duration=1,
            video=VideoStream("h264", 1280, 720, 30, None),
            audio=None,
        ),
    )
    monkeypatch.setattr("videoos.cli.shutil.which", lambda _: "/usr/bin/ffprobe")

    report, _ = _qa_report(output, None, target=TargetSpec(aspect_ratio="9:16", resolution="1080x1920"))

    assert report.passed is False
    assert any(check.name == "output.resolution" and check.status == "fail" for check in report.checks)


def test_render_serializes_unicode_captions_to_managed_artifact(project_fixture, monkeypatch):
    from videoos.core.models import CaptionCue
    from videoos.renderer.ffmpeg import FfmpegRenderer

    timeline_path = project_fixture / "timeline.json"
    timeline = load_model(timeline_path, Timeline)
    timeline.captions = [CaptionCue(start=0, end=1, text="สวัสดี {\\p1}\nworld")]
    save_model_atomic(timeline_path, timeline)
    monkeypatch.setattr("videoos.cli.AnalysisService.analyze", lambda *a, **k: pytest.fail("reanalyzed"))
    monkeypatch.setattr("videoos.cli.CommandRunner.run", lambda *a, **k: type("Result", (), {"stdout": " ... subtitles V->V Render text subtitles\n"})())
    original = FfmpegRenderer.build_plan
    captured = []

    def inspect_caption(self, *args, **kwargs):
        path = kwargs["caption_file"]
        captured.append((path, path.read_text(encoding="utf-8")))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(FfmpegRenderer, "build_plan", inspect_caption)
    result = runner.invoke(app, ["render", str(project_fixture / "project.json"), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert captured and "สวัสดี" in captured[0][1] and "\\p1" not in captured[0][1]
    assert not captured[0][0].exists()


def test_qa_persists_unreadable_container_failure(tmp_path, monkeypatch):
    from videoos.core.errors import ExternalCommandError

    output = tmp_path / "bad.mp4"
    output.write_bytes(b"bad render")
    monkeypatch.setattr("videoos.cli.probe_media", lambda *a: (_ for _ in ()).throw(ExternalCommandError("bad container")))
    result = runner.invoke(app, ["qa", str(output), "--json"])
    assert result.exit_code == 1, result.output
    assert output.with_suffix(".qa.json").is_file()


@pytest.mark.parametrize("occupied", ["render", "qa"])
def test_edit_occupied_output_rejects_before_analysis_or_metadata(tmp_path, monkeypatch, occupied):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "out.mp4"
    (output if occupied == "render" else output.with_suffix(".qa.json")).write_bytes(b"user data")
    monkeypatch.setattr("videoos.cli.AnalysisService.analyze", lambda *a, **k: pytest.fail("analysis started before preflight"))
    result = runner.invoke(app, ["edit", str(source), "--output", str(output)])
    assert result.exit_code != 0
    assert not (tmp_path / "out.videoos").exists()


def test_named_portrait_aspect_derives_matching_dimensions(tmp_path, monkeypatch):
    from tests.unit.factories import make_analysis_fixture
    from videoos.analysis.cache import sha256_file

    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    artifact = make_analysis_fixture(duration=4).model_copy(update={"source_hash": sha256_file(source)})
    monkeypatch.setattr("videoos.cli._analyze", lambda *a, **k: artifact)
    result = runner.invoke(app, ["edit", str(source), "--aspect-ratio", "9:16", "--no-captions", "--dry-run"])
    assert result.exit_code == 0, result.output
    project = load_model(tmp_path / "source.videoos/project.json", ProjectManifest)
    assert project.target.resolution == "1080x1920"
