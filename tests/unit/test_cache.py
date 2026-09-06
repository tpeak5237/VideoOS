import hashlib
from pathlib import Path

from videoos.analysis.cache import AnalysisCache, sha256_file


def test_sha256_file_hashes_source_bytes_without_modifying_source(tmp_path: Path):
    """Catches hash implementations that mutate or misread source media bytes."""
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video-bytes\x00" * 100_000)
    original = source.read_bytes()

    assert sha256_file(source) == hashlib.sha256(original).hexdigest()
    assert source.read_bytes() == original


def test_cache_key_changes_for_source_config_or_tool_fingerprint(tmp_path: Path):
    """Catches stale analysis reuse when any cache-identity input changes."""
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"first")
    cache = AnalysisCache(tmp_path / "cache")
    config = {"silence": 0.5, "scenes": {"threshold": 27}}
    tools = {"ffprobe": "7.0", "scenedetect": "0.6"}

    baseline = cache.key_for(source, config, tools)
    source.write_bytes(b"second")

    assert baseline != cache.key_for(source, config, tools)
    assert baseline != cache.key_for(source, {"scenes": {"threshold": 28}, "silence": 0.5}, tools)
    assert baseline != cache.key_for(source, config, {"ffprobe": "7.1", "scenedetect": "0.6"})


def test_cache_key_is_stable_for_equivalent_mapping_order_and_artifact_uses_hashes(tmp_path: Path):
    """Catches filename-dependent paths and nondeterministic JSON canonicalization."""
    source = tmp_path / "untrusted name ; $(do-not-run).mp4"
    source.write_bytes(b"fixture")
    cache = AnalysisCache(tmp_path / "cache")

    first = cache.key_for(source, {"a": 1, "nested": {"b": 2}}, {"ffprobe": "7.0", "x": "1"})
    second = cache.key_for(source, {"nested": {"b": 2}, "a": 1}, {"x": "1", "ffprobe": "7.0"})
    artifact = cache.artifact_path("a" * 64, "b" * 64, "c" * 64)

    assert first == second
    assert source.name not in str(artifact)
    assert artifact == (
        tmp_path / "cache" / ("a" * 64) / ("b" * 64) / ("c" * 64) / "analysis.json"
    )


def test_artifact_path_changes_when_tool_fingerprint_changes(tmp_path: Path):
    """Catches reuse of one artifact path across analyzer-tool upgrades."""
    cache = AnalysisCache(tmp_path / "cache")

    original = cache.artifact_path("a" * 64, "b" * 64, "c" * 64)
    upgraded = cache.artifact_path("a" * 64, "b" * 64, "d" * 64)

    assert original != upgraded
    assert original.name == upgraded.name == "analysis.json"
