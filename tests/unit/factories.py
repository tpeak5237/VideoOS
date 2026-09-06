from pathlib import Path

from videoos.analysis.models import (
    AnalysisArtifact,
    AudioStream,
    MediaProbe,
    SceneBoundary,
    SilenceRegion,
    SpeechRegion,
    Transcript,
    TranscriptWord,
    VideoStream,
)
from videoos.core.models import (
    ProjectManifest,
    SourceSegment,
    TargetSpec,
    Timeline,
    Track,
)


def make_analysis_fixture(
    *,
    duration: float = 8.0,
    silences: list[tuple[float, float]] | None = None,
    scenes: list[float] | None = None,
    transcript: Transcript | None = None,
    audio: bool = True,
    width: int = 1920,
    height: int = 1080,
    rotation: int | None = 0,
) -> AnalysisArtifact:
    """Return a local, test-only analysis artifact with deterministic defaults."""
    default_transcript = Transcript(
        regions=[SpeechRegion(start=0.0, end=min(duration, 4.0), text="A practical opening")],
        words=[
            TranscriptWord(text="A", start=0.0, end=0.25),
            TranscriptWord(text="practical", start=0.25, end=0.75),
            TranscriptWord(text="opening", start=0.75, end=1.25),
        ],
    )
    return AnalysisArtifact(
        source_hash="a" * 64,
        probe=MediaProbe(
            duration=duration,
            video=VideoStream(
                codec_name="h264", width=width, height=height, frame_rate=30.0, rotation=rotation
            ),
            audio=AudioStream(codec_name="aac", sample_rate=48_000, channels=2) if audio else None,
        ),
        analysis_fingerprint="b" * 64,
        tool_fingerprint="c" * 64,
        silence_regions=[SilenceRegion(start=start, end=end) for start, end in silences or []],
        scene_boundaries=[SceneBoundary(time=time) for time in ([0.0, duration] if scenes is None else scenes)],
        transcript=default_transcript if transcript is None else transcript,
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
