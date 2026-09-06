"""Lazy adapter for the optional, local faster-whisper package."""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

from videoos.analysis.models import (
    CapabilityStatus,
    SpeechRegion,
    Transcript,
    TranscriptWord,
)
from videoos.core.errors import DependencyError


class FasterWhisperTranscriber:
    """Run faster-whisper only when a caller explicitly requests transcription."""

    def __init__(self, model_name: str = "base") -> None:
        self.model_name = model_name

    def availability(self) -> CapabilityStatus:
        available = importlib.util.find_spec("faster_whisper") is not None
        reason = None if available else "faster-whisper is not installed; install with: pip install 'videoos[speech]'"
        return CapabilityStatus(name="faster-whisper", available=available, reason=reason)

    def transcribe(self, path: Path) -> Transcript:
        try:
            faster_whisper = importlib.import_module("faster_whisper")
        except ImportError as error:
            raise DependencyError(
                "faster-whisper is unavailable; install with: pip install 'videoos[speech]'"
            ) from error

        model = faster_whisper.WhisperModel(self.model_name)
        segments, _ = model.transcribe(str(path), word_timestamps=True)
        regions: list[SpeechRegion] = []
        words: list[TranscriptWord] = []
        for segment in segments:
            regions.append(
                SpeechRegion(text=str(segment.text), start=float(segment.start), end=float(segment.end))
            )
            for word in segment.words or ():
                words.append(
                    TranscriptWord(text=str(word.word), start=float(word.start), end=float(word.end))
                )
        return Transcript(provider="faster-whisper", regions=regions, words=words)
