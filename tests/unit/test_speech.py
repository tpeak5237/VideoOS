from pathlib import Path

import pytest

from videoos.analysis.models import Transcript
from videoos.core.errors import DependencyError
from videoos.speech.faster_whisper import FasterWhisperTranscriber
from videoos.speech.protocol import Transcriber, UnavailableTranscriber


def test_unavailable_transcriber_is_explicit():
    result = UnavailableTranscriber("faster-whisper is not installed").availability()

    assert result.available is False
    assert "not installed" in result.reason


def test_unavailable_transcriber_only_raises_when_transcription_is_requested(tmp_path: Path):
    transcriber = UnavailableTranscriber("faster-whisper is not installed")

    assert transcriber.availability().available is False
    with pytest.raises(DependencyError, match="faster-whisper is not installed"):
        transcriber.transcribe(tmp_path / "source.mp4")


def test_transcriber_protocol_describes_local_transcription_contract():
    assert isinstance(UnavailableTranscriber("missing"), Transcriber)
    assert isinstance(FasterWhisperTranscriber(), Transcriber)


def test_faster_whisper_adapter_does_not_initialize_a_model_until_transcribe():
    adapter = FasterWhisperTranscriber()

    assert adapter.model_name == "base"
    assert not hasattr(adapter, "_model")


def test_transcript_words_reject_non_finite_or_reversed_timestamps():
    with pytest.raises(ValueError):
        Transcript(words=[{"text": "bad", "start": float("nan"), "end": 1}])
    with pytest.raises(ValueError):
        Transcript(words=[{"text": "bad", "start": 2, "end": 1}])
