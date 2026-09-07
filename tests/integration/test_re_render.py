import hashlib
import json

import pytest
from typer.testing import CliRunner

from tests.integration.helpers import run_videoos_edit, run_videoos_render
from videoos.cli import app
from videoos.core.io import load_model
from videoos.core.models import ProjectManifest
from videoos.renderer.ffmpeg import FfmpegRenderer


@pytest.mark.integration
def test_timeline_edit_rerenders_without_analysis_or_source_mutation(synthetic_video, tmp_path, monkeypatch):
    """Catches rerendering that reanalyzes, ignores timeline edits, or changes the source."""
    source_hash = hashlib.sha256(synthetic_video.read_bytes()).hexdigest()
    project_dir = run_videoos_edit(synthetic_video, tmp_path / "project")
    project_path = project_dir / "project.json"
    manifest = load_model(project_path, ProjectManifest)
    analysis_path = project_dir / manifest.analysis[0].path
    original_analysis = analysis_path.read_bytes()
    timeline_path = project_dir / "timeline.json"
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    timeline["tracks"][0]["segments"][0]["transform"] = {"zoom_scale": 1.04}
    timeline_path.write_text(json.dumps(timeline), encoding="utf-8")

    planned_graphs = []
    original_build_plan = FfmpegRenderer.build_plan

    def record_plan(self, *args, **kwargs):
        plan = original_build_plan(self, *args, **kwargs)
        planned_graphs.append(plan.filter_graph)
        return plan

    monkeypatch.setattr("videoos.cli.AnalysisService.analyze", lambda *args, **kwargs: pytest.fail("reanalyzed"))
    monkeypatch.setattr("videoos.cli.FfmpegRenderer.build_plan", record_plan)
    original_output = next((project_dir / "renders").glob("*.mp4"))
    original_output_bytes = original_output.read_bytes()
    render_result = run_videoos_render(project_path)
    rerender_output = project_dir / "renders" / "timeline-rerender.mp4"
    rerender_output_bytes = rerender_output.read_bytes()
    occupied_result = CliRunner().invoke(
        app, ["render", str(project_path), "--output", str(rerender_output)]
    )
    qa_result = CliRunner().invoke(
        app, ["qa", str(rerender_output), "--timeline", str(timeline_path), "--json"]
    )

    assert render_result.exit_code == 0, render_result.output
    assert occupied_result.exit_code != 0, occupied_result.output
    assert rerender_output.read_bytes() == rerender_output_bytes
    assert original_output.read_bytes() == original_output_bytes
    assert qa_result.exit_code == 0, qa_result.output
    assert json.loads(qa_result.output)["passed"] is True
    assert planned_graphs and "trunc(iw/1.04/2)*2" in planned_graphs[0]
    assert hashlib.sha256(synthetic_video.read_bytes()).hexdigest() == source_hash
    assert analysis_path.read_bytes() == original_analysis
