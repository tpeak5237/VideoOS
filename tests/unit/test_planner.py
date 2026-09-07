import pytest

from tests.unit.factories import make_analysis_fixture
from videoos.analysis.models import Transcript, TranscriptWord
from videoos.core.models import TargetSpec
from videoos.core.time import TimeRange
from videoos.planner.talking_head import _map_captions, plan_talking_head
from videoos.planner.timeline import source_to_timeline, timeline_to_source
from videoos.profiles.loader import load_profile


def test_source_to_timeline_excludes_removed_range():
    cuts = [TimeRange(start=2.0, end=4.0)]

    assert source_to_timeline(1.0, cuts) == 1.0
    assert source_to_timeline(3.0, cuts) is None
    assert source_to_timeline(5.0, cuts) == 3.0


def test_source_to_timeline_keeps_open_cut_boundaries():
    cuts = [TimeRange(start=2.0, end=4.0)]

    assert source_to_timeline(2.0, cuts) == 2.0
    assert source_to_timeline(4.0, cuts) == 2.0


def test_source_to_timeline_keeps_a_shared_open_boundary_between_adjacent_cuts():
    cuts = [TimeRange(start=1.0, end=2.0), TimeRange(start=2.0, end=3.0)]

    assert source_to_timeline(2.0, cuts) == 1.0


def test_source_to_timeline_merges_overlapping_removed_ranges():
    cuts = [TimeRange(start=2.0, end=4.0), TimeRange(start=3.0, end=5.0)]

    assert source_to_timeline(6.0, cuts) == 3.0


def test_timeline_to_source_maps_sequential_kept_ranges():
    kept = [TimeRange(start=0.0, end=2.0), TimeRange(start=4.0, end=8.0)]

    assert timeline_to_source(1.0, kept) == 1.0
    assert timeline_to_source(3.0, kept) == 5.0


def test_planner_keeps_speech_preserves_centered_pause_and_records_silence_evidence():
    analysis = make_analysis_fixture(silences=[(1.0, 3.0)], duration=8.0)
    target = TargetSpec(aspect_ratio="9:16", resolution="1080x1920")

    timeline = plan_talking_head(analysis, load_profile("talking-head-shortform"), target)

    assert [(segment.source_start, segment.source_end) for segment in timeline.tracks[0].segments] == [
        (0.0, 1.0),
        (1.825, 2.175),
        (3.0, 8.0),
    ]
    assert [(segment.source_start, segment.source_end) for segment in timeline.removed] == [(1.0, 1.825), (2.175, 3.0)]
    assert all(segment.evidence is not None and segment.evidence.reason == "silence" for segment in timeline.removed)
    timeline.validate_against_sources({analysis.source_hash: 8.0})


def test_planner_maps_captions_and_attaches_conservative_target_metadata():
    analysis = make_analysis_fixture(
        duration=8.0,
        silences=[(1.0, 3.0)],
        transcript=Transcript(
            words=[
                TranscriptWord(text="before", start=0.2, end=0.6),
                TranscriptWord(text="removed", start=1.2, end=1.5),
                TranscriptWord(text="after", start=3.2, end=3.6),
            ]
        ),
    )
    timeline = plan_talking_head(
        analysis,
        load_profile("talking-head-shortform"),
        TargetSpec(aspect_ratio="9:16", resolution="1080x1920"),
    )

    assert [cue.text for cue in timeline.captions] == ["before after"]
    assert all(0.0 <= cue.start <= cue.end <= timeline.duration_seconds() for cue in timeline.captions)
    assert all(segment.transform is not None for segment in timeline.tracks[0].segments)
    assert all(segment.audio is not None and segment.audio.target_lufs == -16.0 for segment in timeline.tracks[0].segments)
    assert all(segment.transform.zoom_scale in {None, 1.05} for segment in timeline.tracks[0].segments)


def test_caption_mapping_drops_unicode_word_spanning_a_single_cut():
    cues = _map_captions(
        Transcript(
            words=[
                TranscriptWord(text="ก่อน", start=0.2, end=0.4),
                TranscriptWord(text="ข้าม", start=0.5, end=2.5),
                TranscriptWord(text="หลัง", start=2.6, end=2.8),
            ]
        ),
        [TimeRange(start=1.0, end=2.0)],
        load_profile("talking-head-shortform"),
    )

    assert [cue.text for cue in cues] == ["ก่อน หลัง"]
    assert cues[0].start == pytest.approx(0.2)
    assert cues[0].end == pytest.approx(1.8)


def test_caption_mapping_keeps_unicode_word_ending_at_cut_start():
    cues = _map_captions(
        Transcript(words=[TranscriptWord(text="ก่อน", start=0.2, end=1.0)]),
        [TimeRange(start=1.0, end=2.0)],
        load_profile("talking-head-shortform"),
    )

    assert [(cue.text, cue.start, cue.end) for cue in cues] == [("ก่อน", 0.2, 1.0)]


def test_caption_mapping_keeps_unicode_word_starting_at_cut_end():
    cues = _map_captions(
        Transcript(words=[TranscriptWord(text="หลัง", start=2.0, end=2.4)]),
        [TimeRange(start=1.0, end=2.0)],
        load_profile("talking-head-shortform"),
    )

    assert [(cue.text, cue.start, cue.end) for cue in cues] == [("หลัง", 1.0, 1.4)]


def test_caption_mapping_drops_word_spanning_multiple_cuts():
    cues = _map_captions(
        Transcript(
            words=[
                TranscriptWord(text="before", start=0.2, end=0.4),
                TranscriptWord(text="crosses", start=0.5, end=4.5),
                TranscriptWord(text="after", start=4.6, end=4.8),
            ]
        ),
        [TimeRange(start=1.0, end=2.0), TimeRange(start=3.0, end=4.0)],
        load_profile("talking-head-shortform"),
    )

    assert [cue.text for cue in cues] == ["before", "after"]
    assert all(0.0 <= cue.start <= cue.end for cue in cues)


def test_planner_uses_display_dimensions_for_quarter_turn_rotation():
    timeline = plan_talking_head(
        make_analysis_fixture(width=1080, height=1920, rotation=90),
        load_profile("generic"),
        TargetSpec(aspect_ratio="16:9", resolution="1920x1080"),
    )

    assert all(segment.transform is None for segment in timeline.tracks[0].segments)
