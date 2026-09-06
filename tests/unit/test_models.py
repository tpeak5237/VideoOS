import pytest
from pydantic import ValidationError

from videoos.core.models import (
    AnalysisRef,
    AudioAdjustment,
    CaptionCue,
    DecisionParameters,
    Evidence,
    ProjectManifest,
    SourceSegment,
    TargetSpec,
    Timeline,
    Track,
)

SHA256_A = "a" * 64
SHA256_B = "b" * 64
SHA256_C = "c" * 64


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


def test_analysis_ref_has_validated_deterministic_cache_identity():
    reference = AnalysisRef(
        source_id="main",
        path="analysis/main.json",
        source_sha256=SHA256_A,
        analysis_config_fingerprint=SHA256_B,
        tool_fingerprint=SHA256_C,
    )
    same_reference = reference.model_copy()
    changed_config = reference.model_copy(update={"analysis_config_fingerprint": SHA256_C})

    assert reference.cache_identity == same_reference.cache_identity
    assert reference.cache_identity != changed_config.cache_identity
    with pytest.raises(ValidationError, match="source_sha256"):
        AnalysisRef(
            source_id="main",
            path="analysis/main.json",
            source_sha256="not-a-sha256",
            analysis_config_fingerprint=SHA256_B,
            tool_fingerprint=SHA256_C,
        )


def test_legacy_analysis_ref_loads_but_is_not_cache_reusable():
    reference = AnalysisRef(source_id="main", path="analysis/main.json", cache_key="old-opaque-key")

    assert reference.cache_key == "old-opaque-key"
    assert reference.cache_identity is None
    assert reference.is_cache_reusable is False
    with pytest.raises(ValidationError, match="modern cache identity"):
        AnalysisRef(source_id="main", path="analysis/main.json")


@pytest.mark.parametrize(
    "parameters",
    [
        {"silence_seconds": 600.1},
        {"scene_index": 1_000_001},
    ],
)
def test_decision_parameters_reject_over_limit_values(parameters: dict[str, float | int]):
    with pytest.raises(ValidationError):
        DecisionParameters(**parameters)


def test_manifest_rejects_analysis_reference_for_an_unknown_source():
    with pytest.raises(ValidationError, match="analysis reference"):
        ProjectManifest(
            version="1",
            project_id="demo",
            name="Demo",
            sources=[{"id": "main", "path": "sources/main.mp4"}],
            target=TargetSpec(aspect_ratio="9:16", resolution="1080x1920"),
            analysis=[
                AnalysisRef(
                    source_id="other",
                    path="analysis/other.json",
                    source_sha256=SHA256_A,
                    analysis_config_fingerprint=SHA256_B,
                    tool_fingerprint=SHA256_C,
                )
            ],
        )


def test_decision_fields_reject_arbitrary_prose_but_captions_remain_text():
    with pytest.raises(ValidationError):
        Evidence(action="rm -rf renders", reason="because the model said so", start=0, end=1)
    with pytest.raises(ValidationError):
        SourceSegment(source_id="main", source_end=1, role="shell-command")

    assert CaptionCue(start=0, end=1, text="Free-form subtitle: rm -rf is spoken text.").text


@pytest.mark.parametrize("field,value", [("gain_db", float("nan")), ("gain_db", float("inf")), ("target_lufs", float("-inf")), ("gain_db", 25), ("target_lufs", -71)])
def test_audio_adjustment_rejects_non_finite_and_out_of_range_values(field: str, value: float):
    with pytest.raises(ValidationError):
        AudioAdjustment(**{field: value})


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
