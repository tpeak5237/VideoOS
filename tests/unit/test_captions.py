import pytest

from videoos.analysis.models import Transcript, TranscriptWord
from videoos.captions.models import CaptionStyle
from videoos.captions.segment import segment_transcript
from videoos.captions.serializers import to_ass, to_srt, to_vtt
from videoos.core.models import CaptionCue


def test_caption_segmentation_breaks_by_word_count_and_preserves_unicode():
    transcript = Transcript(
        words=[
            TranscriptWord(text="สวัสดี", start=0.0, end=0.4),
            TranscriptWord(text="โลก", start=0.4, end=0.8),
            TranscriptWord(text="hello", start=0.8, end=1.2),
        ]
    )

    cues = segment_transcript(transcript, max_words_per_line=2, max_duration=2.0)

    assert [cue.text for cue in cues] == ["สวัสดี โลก", "hello"]


def test_caption_segmentation_breaks_before_duration_limit_and_skips_blank_words():
    transcript = Transcript(
        words=[
            TranscriptWord(text=" first ", start=0, end=0.5),
            TranscriptWord(text="   ", start=0.5, end=0.75),
            TranscriptWord(text="second", start=1.1, end=1.5),
        ]
    )

    cues = segment_transcript(transcript, max_words_per_line=3, max_duration=1.0)

    assert [(cue.start, cue.end, cue.text) for cue in cues] == [
        (0.0, 0.5, "first"),
        (1.1, 1.5, "second"),
    ]


def test_caption_segmentation_rejects_an_unsplittable_overlong_word():
    transcript = Transcript(words=[TranscriptWord(text="long", start=0, end=10)])

    with pytest.raises(ValueError, match="word duration"):
        segment_transcript(transcript, max_words_per_line=2, max_duration=2.0)


def test_transcript_rejects_out_of_order_word_starts():
    with pytest.raises(ValueError, match="words must be ordered"):
        Transcript(
            words=[
                TranscriptWord(text="later", start=2, end=3),
                TranscriptWord(text="earlier", start=0, end=1),
            ]
        )


def test_caption_segmentation_defensively_rejects_unsorted_words():
    transcript = Transcript().model_copy(
        update={
            "words": [
                TranscriptWord(text="later", start=2, end=3),
                TranscriptWord(text="earlier", start=0, end=1),
            ]
        }
    )

    with pytest.raises(ValueError, match="words must be ordered"):
        segment_transcript(transcript, max_words_per_line=2, max_duration=2.0)


@pytest.mark.parametrize("max_words_per_line,max_duration", [(0, 2.0), (2, 0.0), (2, float("inf"))])
def test_caption_segmentation_rejects_unbounded_limits(
    max_words_per_line: int, max_duration: float
):
    with pytest.raises(ValueError):
        segment_transcript(Transcript(), max_words_per_line=max_words_per_line, max_duration=max_duration)


def test_srt_and_vtt_use_valid_timestamp_headers():
    cue = CaptionCue(start=0.0, end=1.25, text="hello")

    assert to_srt([cue]).startswith("1\n00:00:00,000 --> 00:00:01,250")
    assert to_vtt([cue]).startswith("WEBVTT\n\n00:00:00.000 --> 00:00:01.250")


@pytest.mark.parametrize("serializer", [to_srt, to_vtt])
def test_srt_and_vtt_reject_descending_cue_starts(serializer):
    cues = [CaptionCue(start=2, end=3, text="later"), CaptionCue(start=0, end=1, text="earlier")]

    with pytest.raises(ValueError, match="cues must be ordered"):
        serializer(cues)


def test_ass_has_deterministic_style_and_escapes_intentional_line_breaks():
    cue = CaptionCue(start=0, end=1.25, text="สวัสดี\nworld")

    rendered = to_ass([cue], CaptionStyle(font_name="Noto Sans Thai", font_size=42))

    assert "Style: Default,Noto Sans Thai,42," in rendered
    assert "Dialogue: 0,0:00:00.00,0:00:01.25,Default,,0,0,0,,สวัสดี\\Nworld" in rendered


@pytest.mark.parametrize("field", ["primary_colour", "outline_colour"])
@pytest.mark.parametrize("value", ["&H00FFFFFF,Injected", "&H00FFFFFF\n[Events]", "#ffffff"])
def test_caption_style_rejects_ass_colour_injection(field: str, value: str):
    with pytest.raises(ValueError, match="ASS colour"):
        CaptionStyle(**{field: value})
