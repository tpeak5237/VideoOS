from pathlib import Path

import pytest

from tests.unit.factories import make_project_and_timeline
from videoos.core.io import save_model_atomic


@pytest.fixture
def project_fixture(tmp_path: Path) -> Path:
    """Persist a valid project whose source is never opened during dry-run rendering."""
    project, timeline = make_project_and_timeline(tmp_path)
    project_dir = tmp_path / "fixture.videoos"
    project_dir.mkdir()
    save_model_atomic(project_dir / "project.json", project)
    save_model_atomic(project_dir / "timeline.json", timeline)
    return project_dir
