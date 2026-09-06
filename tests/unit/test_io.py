from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.unit.factories import make_project_and_timeline
from videoos.core.io import load_model, save_model_atomic
from videoos.core.models import Evidence, ProjectManifest, Timeline


def test_models_round_trip_as_utf8_json(tmp_path: Path):
    manifest, timeline = make_project_and_timeline(tmp_path)
    project_path = tmp_path / "project.json"
    timeline_path = tmp_path / "timeline.json"

    save_model_atomic(project_path, manifest)
    save_model_atomic(timeline_path, timeline)

    assert load_model(project_path, ProjectManifest) == manifest
    assert load_model(timeline_path, Timeline) == timeline
    assert project_path.read_bytes().decode("utf-8").startswith("{")


def test_atomic_save_replaces_existing_json(tmp_path: Path):
    manifest, _ = make_project_and_timeline(tmp_path)
    path = tmp_path / "project.json"
    path.write_text('{"stale": true}', encoding="utf-8")

    save_model_atomic(path, manifest)

    assert load_model(path, ProjectManifest).project_id == "fixture-project"
    assert not list(tmp_path.glob(".project.json.*.tmp"))


def test_load_rejects_invalid_json_with_path_only(tmp_path: Path):
    path = tmp_path / "timeline.json"
    path.write_text('{"private": "unclosed"', encoding="utf-8")

    with pytest.raises(ValueError, match="timeline.json") as exc_info:
        load_model(path, Timeline)

    assert "unclosed" not in str(exc_info.value)


def test_load_rejects_future_versions(tmp_path: Path):
    path = tmp_path / "timeline.json"
    path.write_text('{"version": "2", "tracks": []}', encoding="utf-8")

    with pytest.raises(ValidationError, match="version"):
        load_model(path, Timeline)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_load_rejects_non_standard_json_constants(tmp_path: Path, constant: str):
    path = tmp_path / "timeline.json"
    path.write_text(f'{{"version": {constant}, "tracks": []}}', encoding="utf-8")

    with pytest.raises(ValueError, match="non-standard JSON constant"):
        load_model(path, Timeline)


def test_atomic_save_rejects_non_finite_values_even_if_validation_is_bypassed(tmp_path: Path):
    unsafe = Evidence.model_construct(
        action="remove", reason="silence", confidence=float("nan"), start=0, end=1
    )

    with pytest.raises(ValueError, match="Out of range float values are not JSON compliant"):
        save_model_atomic(tmp_path / "evidence.json", unsafe)
