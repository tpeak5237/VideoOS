"""Real decoded media evidence for the final review, without downloaded fixtures."""

import array
import hashlib
import json
import math
import shutil
import subprocess

import pytest
from typer.testing import CliRunner

from tests.unit.factories import make_analysis_fixture
from videoos.analysis.probe import probe_media
from videoos.analysis.runner import CommandRunner
from videoos.cli import _qa_report, _render, app
from videoos.core.io import save_model_atomic
from videoos.core.models import (
    AudioAdjustment,
    CaptionCue,
    ProjectManifest,
    SourceRef,
    SourceSegment,
    TargetSpec,
    Timeline,
    Track,
    TransformSpec,
)
from videoos.planner.talking_head import plan_talking_head
from videoos.profiles.loader import load_profile
from videoos.renderer.ffmpeg import FfmpegRenderer

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="requires local FFmpeg/ffprobe")]


def make_media(path, *, fps=30, audio=True, black=False):
    visual = "color=c=black:s=320x180" if black else (
        "color=c=red:s=320x180,drawbox=x=106:y=0:w=108:h=180:color=green:t=fill,"
        "drawbox=x=214:y=0:w=106:h=180:color=blue:t=fill")
    args = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"{visual},fps={fps}"]
    if audio:
        args += ["-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=48000"]
    args += ["-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-f", "mp4", str(path)]
    CommandRunner().run(args)
    return path


def project_for(source, *, audio=True, portrait=False):
    return ProjectManifest(version="1", project_id="synthetic", name="synthetic",
        sources=[SourceRef(id="main", path=str(source), has_audio=audio)],
        target=TargetSpec(aspect_ratio="9:16" if portrait else "16:9", resolution="90x160" if portrait else "320x180"))


def timeline_for(**kwargs):
    return Timeline(tracks=[Track(id="video", kind="video", segments=[
        SourceSegment(source_id="main", source_end=2, **kwargs)])])


def render_media(project, timeline, destination):
    renderer = FfmpegRenderer()
    plan = renderer.build_plan(timeline, project, output=destination)
    renderer.render(plan)
    return plan


def raw_frame(path):
    result = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True, timeout=30)
    return result.stdout


def pcm(path):
    result = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-ac", "1", "-ar", "48000", "-f", "f32le", "-"], capture_output=True, check=True, timeout=30)
    samples = array.array("f")
    samples.frombytes(result.stdout)
    return samples


def rms(samples):
    return math.sqrt(sum(value * value for value in samples) / len(samples))


def test_center_crop_observes_green_middle_band_and_exact_display_ratio(tmp_path):
    source = make_media(tmp_path / "bands.mp4", audio=False)
    project = project_for(source, audio=False, portrait=True)
    analysis = make_analysis_fixture(duration=2, audio=False, width=320, height=180)
    timeline = plan_talking_head(analysis, load_profile("generic"), project.target)
    timeline.captions = []
    timeline.tracks[0].segments[0].source_id = "main"
    destination = tmp_path / "portrait.mp4"
    render_media(project, timeline, destination)
    frame = raw_frame(destination)
    red, green, blue = frame[(80 * 90 + 45) * 3:(80 * 90 + 45) * 3 + 3]
    assert green > 100 and red < 20 and blue < 20
    report, _ = _qa_report(destination, timeline, target=project.target, source_durations={"main": 2}, audio_required=False)
    assert next(c for c in report.checks if c.name == "output.display_ratio").status == "pass"


@pytest.mark.parametrize("fps", [24, 30, 60])
def test_zoom_changes_spatial_output_without_changing_time_or_fps(tmp_path, fps):
    source = make_media(tmp_path / "bands.mp4", audio=False, fps=fps)
    project = project_for(source, audio=False)
    normal = tmp_path / "normal.mp4"
    zoomed = tmp_path / "zoomed.mp4"
    render_media(project, timeline_for(), normal)
    render_media(project, timeline_for(transform=TransformSpec(zoom_scale=1.25)), zoomed)
    probe = probe_media(zoomed, CommandRunner())
    assert probe.duration == pytest.approx(2, abs=0.08)
    assert probe.video.frame_rate == pytest.approx(fps, abs=0.01)
    first, second = raw_frame(normal), raw_frame(zoomed)
    assert sum(abs(a-b) for a, b in zip(first, second, strict=True)) / len(first) > 5


def test_manual_audio_gain_fades_and_mixed_silent_sources(tmp_path):
    source = make_media(tmp_path / "audio.mp4")
    silent = make_media(tmp_path / "silent.mp4", audio=False)
    project = project_for(source)
    base = tmp_path / "base.mp4"
    adjusted = tmp_path / "adjusted.mp4"
    render_media(project, timeline_for(), base)
    plan = render_media(project, timeline_for(audio=AudioAdjustment(gain_db=-20, fade_in_seconds=0.5, fade_out_seconds=0.5)), adjusted)
    assert "volume=-20dB" in plan.filter_graph
    original, changed = pcm(base), pcm(adjusted)
    attenuation = 20 * math.log10(rms(changed[36000:60000]) / rms(original[36000:60000]))
    assert attenuation == pytest.approx(-20, abs=0.7)
    assert rms(changed[:4800]) < rms(changed[36000:60000]) * 0.25
    assert rms(changed[91200:96000]) < rms(changed[36000:60000]) * 0.25
    project.sources.append(SourceRef(id="silent", path=str(silent), has_audio=False))
    timeline = timeline_for()
    timeline.tracks[0].segments.append(SourceSegment(source_id="silent", source_end=2, timeline_start=2))
    mixed = tmp_path / "mixed.mp4"
    plan = render_media(project, timeline, mixed)
    assert "[1:a" not in plan.filter_graph
    sound = pcm(mixed)
    assert rms(sound[:48000]) > 0.01 and rms(sound[120000:168000]) < 0.0001
    assert probe_media(mixed, CommandRunner()).duration == pytest.approx(4, abs=0.1)


def test_requested_lufs_affects_real_output(tmp_path):
    source = make_media(tmp_path / "audio.mp4")
    output = tmp_path / "normalized.mp4"
    plan = render_media(project_for(source), timeline_for(audio=AudioAdjustment(target_lufs=-25)), output)
    assert "loudnorm=I=-25:" in plan.filter_graph and "loudnorm=I=-16:" not in plan.filter_graph
    result = CommandRunner().run(["ffmpeg", "-hide_banner", "-i", str(output), "-af", "loudnorm=print_format=json", "-f", "null", "-"])
    measured, _ = json.JSONDecoder().raw_decode(result.stderr[result.stderr.rfind("{"):])
    assert float(measured["input_i"]) == pytest.approx(-25, abs=1)


def test_black_and_audio_qa_use_real_measurements(tmp_path):
    source = make_media(tmp_path / "black.mp4", black=True)
    report, report_path = _qa_report(source, None, audio_required=True)
    checks = {c.name: c for c in report.checks}
    assert checks["output.black_frame_start"].status == "warn"
    assert checks["output.black_frame_end"].status == "warn"
    assert checks["output.audio_peak"].evidence["peak_dbfs"] is not None
    assert report_path.is_file()
    silent = make_media(tmp_path / "no-audio.mp4", audio=False)
    missing, _ = _qa_report(silent, None, audio_required=True)
    assert not missing.passed
    assert next(c for c in missing.checks if c.name == "output.audio_stream").status == "fail"


def test_edit_repeat_and_metadata_named_source_are_non_destructive(tmp_path):
    source = make_media(tmp_path / "timeline.json")
    before = source.read_bytes()
    result = CliRunner().invoke(app, ["edit", str(source), "--output", str(tmp_path)])
    assert result.exit_code != 0
    assert source.read_bytes() == before
    assert not (tmp_path / "project.json").exists()
    project = tmp_path / "new-project"
    command = ["edit", str(source), "--output", str(project), "--resolution", "320x180"]
    first = CliRunner().invoke(app, command)
    assert first.exit_code == 0, first.output
    timeline_path = project / "timeline.json"
    timeline = json.loads(timeline_path.read_text())
    timeline["captions"] = [{"start": 0, "end": 1, "text": "user edit"}]
    timeline_path.write_text(json.dumps(timeline))
    snapshot = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    assert CliRunner().invoke(app, command).exit_code != 0
    assert all(p.read_bytes() == value for p, value in snapshot.items())
    assert hashlib.sha256(source.read_bytes()).digest() == hashlib.sha256(before).digest()


def test_shorts_preserve_audio_and_emit_qa_and_reject_repeat(tmp_path):
    source = make_media(tmp_path / "short.mp4")
    destination = tmp_path / "shorts"
    command = ["shorts", str(source), "--count", "1", "--output-dir", str(destination)]
    result = CliRunner().invoke(app, command)
    assert result.exit_code == 0, result.output
    output = next(destination.rglob("*.mp4"))
    assert probe_media(output, CommandRunner()).audio is not None
    assert json.loads(output.with_suffix(".qa.json").read_text())["passed"]
    snapshot = {p: p.read_bytes() for p in destination.rglob("*") if p.is_file()}
    assert CliRunner().invoke(app, command).exit_code != 0
    assert all(p.read_bytes() == value for p, value in snapshot.items())


def test_caption_render_capability_or_decoded_burn_in_without_analysis(tmp_path, monkeypatch):
    source = make_media(tmp_path / "source.mp4", audio=False)
    project = project_for(source, audio=False)
    timeline = timeline_for()
    timeline.captions = [CaptionCue(start=0, end=1, text="Hello สวัสดี")]
    save_model_atomic(tmp_path / "project.json", project)
    save_model_atomic(tmp_path / "timeline.json", timeline)
    monkeypatch.setattr("videoos.cli.AnalysisService.analyze", lambda *a, **k: pytest.fail("reanalyzed"))
    output = tmp_path / "captioned.mp4"
    filters = CommandRunner().run(["ffmpeg", "-hide_banner", "-filters"]).stdout
    if not any(len(line.split()) > 1 and line.split()[1] == "subtitles" for line in filters.splitlines()):
        result = CliRunner().invoke(app, ["render", str(tmp_path / "project.json"), "--output", str(output)])
        assert result.exit_code != 0 and "caption burn-in unavailable" in result.output
        assert not output.exists()
        return
    result = _render(tmp_path / "project.json", output=output, dry_run=False)
    assert result["qa_passed"]
    baseline = tmp_path / "baseline.mp4"
    render_media(project, timeline_for(), baseline)
    assert raw_frame(output) != raw_frame(baseline)


@pytest.mark.parametrize("command", ["edit", "render", "shorts"])
def test_media_commands_fail_after_persisting_failed_qa(tmp_path, monkeypatch, command):
    from videoos.qa.models import QACheck

    source = make_media(tmp_path / "source.mp4", audio=False)
    monkeypatch.setattr("videoos.cli.check_output", lambda *a, **k: [
        QACheck(name="output.duration", status="fail", message="injected measured duration mismatch")])
    if command == "render":
        save_model_atomic(tmp_path / "project.json", project_for(source, audio=False))
        save_model_atomic(tmp_path / "timeline.json", timeline_for())
        args = ["render", str(tmp_path / "project.json"), "--output", str(tmp_path / "out.mp4")]
    elif command == "edit":
        args = ["edit", str(source), "--output", str(tmp_path / "project"), "--resolution", "320x180"]
    else:
        args = ["shorts", str(source), "--count", "1", "--output-dir", str(tmp_path / "shorts")]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 1, result.output
    reports = list(tmp_path.rglob("*.qa.json"))
    assert reports and all(json.loads(path.read_text())["passed"] is False for path in reports)


def test_qa_source_bounds_use_verified_context_or_warn(tmp_path):
    source = make_media(tmp_path / "source.mp4", audio=False)
    project = project_for(source, audio=False)
    timeline = timeline_for()
    timeline.tracks[0].segments = [
        SourceSegment(source_id="main", source_start=1, source_end=2),
        SourceSegment(source_id="main", source_start=0, source_end=1, timeline_start=1)]
    save_model_atomic(tmp_path / "project.json", project)
    save_model_atomic(tmp_path / "timeline.json", timeline)
    args = ["qa", str(source), "--timeline", str(tmp_path / "timeline.json"), "--json"]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert next(c for c in json.loads(result.output)["checks"] if c["name"] == "timeline.source_bounds")["status"] == "pass"
    timeline.tracks[0].segments = [SourceSegment(source_id="main", source_start=6, source_end=8)]
    save_model_atomic(tmp_path / "timeline.json", timeline)
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 1, result.output
    detached = tmp_path / "detached"
    detached.mkdir()
    save_model_atomic(detached / "timeline.json", timeline)
    result = CliRunner().invoke(app, ["qa", str(source), "--timeline", str(detached / "timeline.json"), "--json"])
    assert result.exit_code == 0, result.output
    assert next(c for c in json.loads(result.output)["checks"] if c["name"] == "timeline.source_bounds")["status"] == "warn"


def test_render_relative_source_ignores_competing_cwd_and_stale_audio_flag(tmp_path, monkeypatch):
    source = make_media(tmp_path / "source.mp4", audio=True)
    project = project_for(source, audio=False)  # Untrusted declaration must be reverified.
    project.sources[0].path = "source.mp4"
    save_model_atomic(tmp_path / "project.json", project)
    save_model_atomic(tmp_path / "timeline.json", timeline_for())
    unrelated = tmp_path / "elsewhere"
    unrelated.mkdir()
    make_media(unrelated / "source.mp4", audio=False, black=True)
    monkeypatch.chdir(unrelated)
    result = _render(tmp_path / "project.json", output=tmp_path / "resolved.mp4", dry_run=False)
    assert result["qa_passed"]
    assert probe_media(tmp_path / "resolved.mp4", CommandRunner()).audio is not None
