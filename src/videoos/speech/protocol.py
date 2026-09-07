"""Provider-neutral contracts for optional local transcription."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from videoos.analysis.models import CapabilityStatus, Transcript
from videoos.core.errors import DependencyError


@runtime_checkable
class Transcriber(Protocol):
    """A local speech-to-text provider that never alters source media."""

    def transcribe(self, path: Path) -> Transcript: ...

    def availability(self) -> CapabilityStatus: ...


class UnavailableTranscriber:
    """An explicit optional-provider absence that fails only on use."""

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def availability(self) -> CapabilityStatus:
        return CapabilityStatus(name="speech", available=False, reason=self.reason)

    def transcribe(self, path: Path) -> Transcript:
        raise DependencyError(self.reason)
