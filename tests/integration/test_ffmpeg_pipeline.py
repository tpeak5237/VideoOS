import hashlib
import json

import pytest
from typer.testing import CliRunner

from tests.integration.helpers import run_videoos_edit
from videoos.cli import app
from videoos.core.io import load_model
from videoos.core.models import ProjectManifest, Timeline
from videoos.qa.models import QAReport


@pytest.mark.integration
def test_analyze_edit_render_and_qa_preserve_the_synthetic_source(synthetic_video, tmp_path, monkeypatch):
    """Catches a pipeline that mutates input, loses streams, or emits a failed QA report."""
    source_hash = hashlib.sha256(synthetic_video.read_bytes()).hexdigest()
    analysis_output = tmp_path / "analysis.json"
    analysis_result = CliRunner().invoke(
        app, ["analyze", str(synthetic_video), "--output", str(analysis_output), "--json"]
    )

    assert analysis_result.exit_code == 0, analysis_result.output
    assert analysis_output.exists()

    analysis_payload = json.loads(analysis_output.read_text(encoding="utf-8"))
    assert any(
        region["end"] - region["start"] >= 0.9
        for region in analysis_payload["silence_regions"]
    )
    cache_artifacts = list((tmp_path / ".videoos-cache" / source_hash).rglob("analysis.json"))
    assert len(cache_artifacts) == 1
    monkeypatch.setattr(
        "videoos.analysis.service.probe_media",
        lambda *args, **kwargs: pytest.fail("analysis cache was not reused"),
    )

    project_dir = run_videoos_edit(synthetic_video, tmp_path / "project")
    project_path = project_dir / "project.json"
    timeline_path = project_dir / "timeline.json"
    manifest = load_model(project_path, ProjectManifest)
    timeline = load_model(timeline_path, Timeline)
    analysis_path = project_dir / manifest.analysis[0].path
    output = next((project_dir / "renders").glob("*.mp4"))
    qa_path = output.with_suffix(".qa.json")
    qa = load_model(qa_path, QAReport)

    assert hashlib.sha256(synthetic_video.read_bytes()).hexdigest() == source_hash
    assert manifest.sources[0].id == source_hash
    assert manifest.analysis[0].source_sha256 == source_hash
    assert analysis_payload["source_hash"] == source_hash
    assert json.loads(analysis_path.read_text(encoding="utf-8"))["source_hash"] == source_hash
    assert output.stat().st_size > 0
    assert qa.passed is True
    assert qa.resolution == manifest.target.resolution
    assert qa.duration == pytest.approx(timeline.duration_seconds(), abs=0.15)
    assert any(check.name == "output.video_stream" and check.status == "pass" for check in qa.checks)
    assert any(check.name == "output.audio_stream" and check.status == "pass" for check in qa.checks)
