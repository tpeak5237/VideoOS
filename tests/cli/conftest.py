from pathlib import Path

import pytest

from tests.unit.factories import make_analysis_fixture, make_project_and_timeline
from videoos.analysis.cache import sha256_file
from videoos.core.io import save_model_atomic
from videoos.core.models import AnalysisRef, SourceRef


@pytest.fixture
def project_fixture(tmp_path: Path) -> Path:
    """Persist a valid project with a source-verified analysis artifact."""
    project, timeline = make_project_and_timeline(tmp_path)
    project_dir = tmp_path / "fixture.videoos"
    project_dir.mkdir()
    source_path = Path(project.sources[0].path)
    source_hash = sha256_file(source_path)
    artifact = make_analysis_fixture(duration=4).model_copy(update={"source_hash": source_hash})
    analysis_path = project_dir / "analysis" / f"{source_hash}.json"
    analysis_path.parent.mkdir()
    project = project.model_copy(
        update={
            "sources": [SourceRef(id=source_hash, path=str(source_path))],
            "analysis": [
                AnalysisRef(
                    source_id=source_hash,
                    path=str(analysis_path.relative_to(project_dir)),
                    source_sha256=source_hash,
                    analysis_config_fingerprint=artifact.analysis_fingerprint,
                    tool_fingerprint=artifact.tool_fingerprint,
                )
            ],
        }
    )
    timeline = timeline.model_copy(
        update={
            "tracks": [
                track.model_copy(
                    update={
                        "segments": [
                            segment.model_copy(update={"source_id": source_hash})
                            for segment in track.segments
                        ]
                    }
                )
                for track in timeline.tracks
            ]
        }
    )
    save_model_atomic(analysis_path, artifact)
    save_model_atomic(project_dir / "project.json", project)
    save_model_atomic(project_dir / "timeline.json", timeline)
    return project_dir
