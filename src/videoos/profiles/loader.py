"""Load validated built-in and caller-owned edit policy profiles."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import yaml

from .models import Profile

_BUILTINS_DIR = Path(__file__).with_name("builtins")
_SUPPORTED_SUFFIXES = {".json", ".yaml", ".yml"}


def _builtin_path(name: str) -> Path | None:
    if not name or Path(name).name != name:
        return None
    path = _BUILTINS_DIR / f"{name}.yaml"
    return path if path.is_file() else None


def _resolve_profile_path(name_or_path: str) -> Path:
    builtin = _builtin_path(name_or_path)
    if builtin is not None:
        return builtin.resolve()
    path = Path(name_or_path).expanduser()
    if path.suffix.lower() not in _SUPPORTED_SUFFIXES:
        raise ValueError("profile must be an exact built-in slug or a .yaml, .yml, or .json file")
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"profile file does not exist: {resolved}")
    return resolved


def _read_payload(path: Path) -> Mapping[str, object]:
    text = path.read_text(encoding="utf-8")
    loaded = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    if not isinstance(loaded, Mapping):
        raise TypeError("profile root must be a mapping")
    return loaded


def load_profile(name_or_path: str) -> Profile:
    """Return one strict, provenance-carrying profile without network access."""
    path = _resolve_profile_path(name_or_path)
    payload = dict(_read_payload(path))
    if "provenance" in payload:
        raise ValueError("profile provenance is assigned by the loader")
    payload["provenance"] = str(path)
    return Profile.model_validate(payload)
