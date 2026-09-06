"""CLI helpers that retain command output when an integration command fails."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from videoos.cli import app


def run_videoos_edit(source: Path, project_root: Path) -> Path:
    """Create and render a project through the public edit command."""
    result = CliRunner().invoke(app, ["edit", str(source), "--output", str(project_root)])
    assert result.exit_code == 0, result.output
    return project_root


def run_videoos_render(project_json: Path):
    """Render an existing project to a new managed destination through the public CLI."""
    output = project_json.parent / "renders" / "timeline-rerender.mp4"
    result = CliRunner().invoke(app, ["render", str(project_json), "--output", str(output)])
    assert result.exit_code == 0, result.output
    return result
