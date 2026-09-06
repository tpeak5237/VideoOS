"""Content-addressed local analysis cache identity helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

_CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of an existing source file without modifying it."""
    source = path.resolve(strict=True)
    digest = hashlib.sha256()
    with source.open("rb") as file_handle:
        while chunk := file_handle.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(value: Mapping[str, object]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validated_digest(value: str, name: str) -> str:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


class AnalysisCache:
    """Derive stable local cache keys from source and analysis fingerprints."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir.resolve(strict=False)

    def key_for(
        self,
        path: Path,
        config: Mapping[str, object],
        tool_versions: Mapping[str, str],
    ) -> str:
        source_hash = sha256_file(path)
        config_hash = _canonical_hash(config)
        tool_hash = _canonical_hash(tool_versions)
        identity = f"{source_hash}\0{config_hash}\0{tool_hash}"
        return hashlib.sha256(identity.encode("ascii")).hexdigest()

    def artifact_path(self, source_hash: str, config_hash: str, tool_hash: str) -> Path:
        """Return a complete filename-independent address for an analysis artifact."""
        source_digest = _validated_digest(source_hash, "source_hash")
        config_digest = _validated_digest(config_hash, "config_hash")
        tool_digest = _validated_digest(tool_hash, "tool_hash")
        return self.cache_dir / source_digest / config_digest / tool_digest / "analysis.json"
