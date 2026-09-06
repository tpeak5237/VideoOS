"""Deterministic conversion from transcript words to caption cues."""

from __future__ import annotations

import math

from videoos.analysis.models import Transcript, TranscriptWord
from videoos.core.models import CaptionCue


def _validate_limits(max_words_per_line: int, max_duration: float) -> float:
    if max_words_per_line < 1:
        raise ValueError("max_words_per_line must be at least 1")
    duration = float(max_duration)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("max_duration must be finite and greater than zero")
    return duration


def segment_transcript(
    transcript: Transcript, *, max_words_per_line: int, max_duration: float
) -> list[CaptionCue]:
    """Group non-empty transcript words without crossing count or duration limits."""
    duration_limit = _validate_limits(max_words_per_line, max_duration)
    cues: list[CaptionCue] = []
    current_words: list[TranscriptWord] = []

    def flush() -> None:
        if not current_words:
            return
        cues.append(
            CaptionCue(
                start=current_words[0].start,
                end=current_words[-1].end,
                text=" ".join(word.text.strip() for word in current_words),
            )
        )
        current_words.clear()

    for word in transcript.words:
        normalized = word.text.strip()
        if not normalized:
            continue
        normalized_word = word.model_copy(update={"text": normalized})
        exceeds_count = len(current_words) >= max_words_per_line
        exceeds_duration = bool(current_words) and normalized_word.end - current_words[0].start > duration_limit
        if exceeds_count or exceeds_duration:
            flush()
        current_words.append(normalized_word)
    flush()
    return cues
