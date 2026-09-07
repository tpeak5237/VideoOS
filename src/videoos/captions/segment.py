"""Deterministic conversion from transcript words to caption cues."""

from __future__ import annotations

import math
from itertools import pairwise

from videoos.analysis.models import Transcript, TranscriptWord
from videoos.core.models import CaptionCue


def _validate_limits(max_words_per_line: int, max_duration: float) -> float:
    if max_words_per_line < 1:
        raise ValueError("max_words_per_line must be at least 1")
    duration = float(max_duration)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("max_duration must be finite and greater than zero")
    return duration


def _validate_word_order(words: list[TranscriptWord]) -> None:
    if any(current.start < previous.start for previous, current in pairwise(words)):
        raise ValueError("words must be ordered by nondecreasing start timestamp")


def segment_transcript(
    transcript: Transcript, *, max_words_per_line: int, max_duration: float
) -> list[CaptionCue]:
    """Group ordered words; reject unsplittable words exceeding the duration limit."""
    duration_limit = _validate_limits(max_words_per_line, max_duration)
    _validate_word_order(transcript.words)
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
        if normalized_word.end - normalized_word.start > duration_limit:
            raise ValueError("word duration exceeds max_duration and cannot be split safely")
        exceeds_count = len(current_words) >= max_words_per_line
        exceeds_duration = bool(current_words) and normalized_word.end - current_words[0].start > duration_limit
        if exceeds_count or exceeds_duration:
            flush()
        current_words.append(normalized_word)
    flush()
    return cues
