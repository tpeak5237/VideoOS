import pytest
from pydantic import ValidationError

from videoos.core.models import (
    CaptionCue,
    Evidence,
    ProjectManifest,
    SourceSegment,
    TargetSpec,
    Timeline,
    Track,
)


def test_manifest_has_explicit_version_and_target():
    manifest = ProjectManifest(
        version="1",
        project_id="demo",
        name="Demo",
        sources=[{"id": "main", "path": "sources/main.mp4"}],
        target=TargetSpec(aspect_ratio="9:16", resolution="1080x1920"),
    )
    assert manifest.version == "1"
    assert manifest.target.width == 1080
    assert manifest.target.height == 1920


def test_source_segment_rejects_reversed_and_nan_ranges():
    with pytest.raises((ValidationError, ValueError)):
        SourceSegment(source_id="main", source_start=5, source_end=2)
    with pytest.raises((ValidationError, ValueError)):
        SourceSegment(source_id="main", source_start=float("nan"), source_end=2)


def test_timeline_rejects_same_track_overlap():
    timeline = Timeline(
        tracks=[
            Track(
                id="video",
                kind="video",
                segments=[
                    SourceSegment(source_id="main", source_start=0, source_end=2, timeline_start=0),
                    SourceSegment(
                        source_id="main", source_start=2, source_end=4, timeline_start=1.5
                    ),
                ],
            )
        ]
    )
    with pytest.raises(ValueError, match="overlap"):
        timeline.validate_against_sources({"main": 10})


def test_evidence_is_serializable_and_explainable():
    evidence = Evidence(action="remove", reason="silence", confidence=0.99, start=2, end=4)
    assert evidence.model_dump(mode="json")["reason"] == "silence"


def test_timeline_rejects_unknown_sources_and_out_of_bounds_captions():
    timeline = Timeline(
        tracks=[Track(id="video", kind="video", segments=[SourceSegment(source_id="unknown", source_end=4)])],
        captions=[CaptionCue(start=3, end=5, text="Hello")],
    )
    with pytest.raises(ValueError, match="unknown source"):
        timeline.validate_against_sources({"main": 4})

    bounded = timeline.model_copy(
        update={
            "tracks": [
                Track(id="video", kind="video", segments=[SourceSegment(source_id="main", source_end=4)])
            ]
        }
    )
    with pytest.raises(ValueError, match="caption"):
        bounded.validate_against_sources({"main": 4})
