from pathlib import Path

from videoos.core.models import (
    ProjectManifest,
    SourceSegment,
    TargetSpec,
    Timeline,
    Track,
)


def make_project_and_timeline(tmp_path: Path) -> tuple[ProjectManifest, Timeline]:
    source_path = tmp_path / "sources" / "fixture.mp4"
    source_path.parent.mkdir(exist_ok=True)
    source_path.write_bytes(b"fixture-media")
    manifest = ProjectManifest(
        version="1",
        project_id="fixture-project",
        name="Fixture project",
        sources=[{"id": "main", "path": str(source_path)}],
        target=TargetSpec(aspect_ratio="16:9", resolution="1920x1080"),
    )
    timeline = Timeline(
        version="1",
        tracks=[
            Track(
                id="video",
                kind="video",
                segments=[SourceSegment(source_id="main", source_start=0, source_end=4)],
            )
        ],
    )
    return manifest, timeline
