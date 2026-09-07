"""Optional, local-only speech transcription adapters."""

from .faster_whisper import FasterWhisperTranscriber
from .protocol import Transcriber, UnavailableTranscriber

__all__ = ["FasterWhisperTranscriber", "Transcriber", "UnavailableTranscriber"]
