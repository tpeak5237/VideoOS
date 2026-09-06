from pathlib import Path

import pytest

from videoos import __version__
from videoos.core.errors import UnsafePathError
from videoos.core.paths import resolve_input_path
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
