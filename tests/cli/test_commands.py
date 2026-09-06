from typer.testing import CliRunner

from videoos.analysis.models import MediaProbe, VideoStream
from videoos.cli import _qa_report, app
from videoos.core.models import TargetSpec

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
