"""Unicode-safe, deterministic subtitle serializers."""

from __future__ import annotations

import math
from collections.abc import Iterable

from videoos.core.models import CaptionCue
from videoos.core.time import finite_non_negative

from .models import CaptionStyle


def _milliseconds(value: float) -> int:
    return round(finite_non_negative(value, "timestamp") * 1000)


def _srt_timestamp(value: float) -> str:
    hours, remainder = divmod(_milliseconds(value), 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _vtt_timestamp(value: float) -> str:
    return _srt_timestamp(value).replace(",", ".")


def _ass_timestamp(value: float) -> str:
    centiseconds = round(finite_non_negative(value, "timestamp") * 100)
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    seconds, hundredths = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{hundredths:02d}"


def _cue_text(cue: CaptionCue) -> str:
    return str(cue.text).replace("\r\n", "\n").replace("\r", "\n")


def _validated_cues(cues: Iterable[CaptionCue]) -> list[CaptionCue]:
    result = list(cues)
    previous_start: float | None = None
    for cue in result:
        start = finite_non_negative(cue.start, "cue start")
        end = finite_non_negative(cue.end, "cue end")
        if end < start:
            raise ValueError("cue end must be greater than or equal to cue start")
        if previous_start is not None and start < previous_start:
            raise ValueError("cues must be ordered by nondecreasing start timestamp")
        previous_start = start
    return result


def to_srt(cues: Iterable[CaptionCue]) -> str:
    """Serialize cues to standard UTF-8-safe SRT text."""
    blocks = [
        f"{index}\n{_srt_timestamp(cue.start)} --> {_srt_timestamp(cue.end)}\n{_cue_text(cue)}"
        for index, cue in enumerate(_validated_cues(cues), start=1)
    ]
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def to_vtt(cues: Iterable[CaptionCue]) -> str:
    """Serialize cues to WebVTT text with a required header."""
    blocks = [
        f"{_vtt_timestamp(cue.start)} --> {_vtt_timestamp(cue.end)}\n{_cue_text(cue)}"
        for cue in _validated_cues(cues)
    ]
    return "WEBVTT\n\n" + "\n\n".join(blocks) + ("\n" if blocks else "")


def _ass_text(value: str) -> str:
    # ASS has executable override blocks and backslash escapes, not a general
    # literal-text quoting mechanism. Render those three characters as visible
    # fullwidth punctuation; only serializer-owned line breaks become escapes.
    if any(ord(character) < 32 and character not in "\n\t" for character in value):
        raise ValueError("caption text contains unsupported control characters")
    return value.translate(str.maketrans({"\\": "＼", "{": "｛", "}": "｝", "\n": "\\N"}))


def _ass_number(value: float) -> str:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError("ASS style dimensions must be finite")
    return f"{numeric:g}"


def to_ass(cues: Iterable[CaptionCue], style: CaptionStyle) -> str:
    """Serialize cues to ASS with one deterministic default style."""
    header = "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            "",
            "[V4+ Styles]",
            (
                "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
                "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
                "Alignment,MarginL,MarginR,MarginV,Encoding"
            ),
            (
                "Style: Default,"
                f"{style.font_name},{_ass_number(style.font_size)},{style.primary_colour},&H000000FF,"
                f"{style.outline_colour},&H00000000,0,0,0,0,100,100,0,0,1,{_ass_number(style.outline)},"
                f"{_ass_number(style.shadow)},{style.alignment},24,24,{style.margin_v},1"
            ),
            "",
            "[Events]",
            "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
        ]
    )
    lines = [
        "Dialogue: 0,"
        f"{_ass_timestamp(cue.start)},{_ass_timestamp(cue.end)},Default,,0,0,0,,{_ass_text(_cue_text(cue))}"
        for cue in _validated_cues(cues)
    ]
    return header + "\n" + "\n".join(lines) + "\n"
