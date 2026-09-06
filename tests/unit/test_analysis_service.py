from pathlib import Path

import pytest

from videoos.analysis.models import AnalysisConfig, MediaProbe, VideoStream
from videoos.analysis.service import AnalysisService


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def run(self, args: list[str]) -> object:
        self.calls.append(args)
        return type("Result", (), {"stdout": "", "stderr": ""})()

    def calls_for(self, executable: str) -> int:
        return sum(args[0] == executable for args in self.calls)


def make_service_with_fake_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AnalysisService:
    """Build a real cache-backed service while replacing only media-tool boundaries."""
    from videoos.analysis import service as service_module

    runner = RecordingRunner()
    def fake_probe(path: Path, active_runner: RecordingRunner) -> MediaProbe:
        active_runner.run(["ffprobe", str(path)])
        return MediaProbe(
            duration=4.0,
            video=VideoStream("h264", 640, 360, 30.0, None),
            audio=None,
        )

    monkeypatch.setattr(service_module, "probe_media", fake_probe)
    monkeypatch.setattr(service_module, "detect_silence", lambda *args, **kwargs: [])
    monkeypatch.setattr(service_module, "detect_scenes", lambda *args, **kwargs: [])
    return AnalysisService(cache_dir=tmp_path / "cache", runner=runner)


def test_cached_analysis_does_not_call_probe_twice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Catches cache misses that repeatedly invoke local ffprobe for identical identity."""
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fixture")
    service = make_service_with_fake_probe(tmp_path, monkeypatch)
    config = AnalysisConfig()

    first = service.analyze(source, config=config)
    second = service.analyze(source, config=config)

    assert first.source_hash == second.source_hash
    assert service.runner.calls_for("ffprobe") == 1


def test_analysis_without_audio_skips_silence_and_records_capability(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Catches invoking an audio filter for media whose probe has no audio stream."""
    source = tmp_path / "silent.mp4"
    source.write_bytes(b"fixture")
    service = make_service_with_fake_probe(tmp_path, monkeypatch)

    artifact = service.analyze(source, config=AnalysisConfig())

    assert artifact.silence_regions == []
    assert any(status.name == "silence" and not status.available for status in artifact.capabilities)
