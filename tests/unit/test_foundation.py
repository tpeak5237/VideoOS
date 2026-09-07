from pathlib import Path

import pytest

from videoos import __version__
from videoos.core.errors import UnsafePathError
from videoos.core.paths import publish_staged_output, resolve_input_path
from videoos.core.time import finite_non_negative


def test_package_exposes_semver_version():
    assert __version__.split(".")[:2] == ["0", "1"]


def test_path_resolver_returns_absolute_existing_path(tmp_path: Path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fixture")
    assert resolve_input_path("clip.mp4", base_dir=tmp_path) == source.resolve()


def test_path_resolver_rejects_parent_escape(tmp_path: Path):
    with pytest.raises(UnsafePathError):
        resolve_input_path("../outside.mp4", base_dir=tmp_path)


def test_time_rejects_non_finite_values():
    with pytest.raises(ValueError, match="finite"):
        finite_non_negative(float("nan"), "start")


def test_publish_staged_output_exclusively_publishes_and_removes_stage(tmp_path: Path):
    staged = tmp_path / ".clip.mp4.part"
    destination = tmp_path / "clip.mp4"
    staged.write_bytes(b"rendered")

    assert publish_staged_output(staged, destination, project_dir=tmp_path) == destination
    assert destination.read_bytes() == b"rendered"
    assert not staged.exists()


def test_publish_staged_output_rejects_existing_target_without_changing_it(tmp_path: Path):
    staged = tmp_path / ".clip.mp4.part"
    destination = tmp_path / "clip.mp4"
    staged.write_bytes(b"new")
    destination.write_bytes(b"original")

    with pytest.raises(FileExistsError):
        publish_staged_output(staged, destination, project_dir=tmp_path)

    assert destination.read_bytes() == b"original"
    assert staged.read_bytes() == b"new"


def test_publish_staged_output_does_not_follow_existing_symlink(tmp_path: Path):
    staged = tmp_path / ".clip.mp4.part"
    destination = tmp_path / "clip.mp4"
    outside = tmp_path / "outside.mp4"
    staged.write_bytes(b"new")
    outside.write_bytes(b"outside")
    destination.symlink_to(outside)

    with pytest.raises(FileExistsError):
        publish_staged_output(staged, destination, project_dir=tmp_path)

    assert outside.read_bytes() == b"outside"
    assert destination.is_symlink()


def test_publish_staged_output_rejects_existing_hard_link_target(tmp_path: Path):
    staged = tmp_path / ".clip.mp4.part"
    destination = tmp_path / "clip.mp4"
    existing = tmp_path / "existing.mp4"
    staged.write_bytes(b"new")
    existing.write_bytes(b"original")
    destination.hardlink_to(existing)

    with pytest.raises(FileExistsError):
        publish_staged_output(staged, destination, project_dir=tmp_path)

    assert existing.read_bytes() == b"original"
