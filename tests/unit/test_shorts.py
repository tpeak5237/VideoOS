from tests.unit.factories import make_analysis_fixture
from videoos.analysis.models import SpeechRegion, Transcript
from videoos.planner.shorts import score_short_candidates


def test_short_candidates_are_bounded_and_scored():
    candidates = score_short_candidates(make_analysis_fixture(duration=45.0), count=3)

    assert len(candidates) <= 3
    assert all(0.0 <= item.score <= 1.0 for item in candidates)
    assert all(15.0 <= item.duration_seconds <= 45.0 for item in candidates)


def test_short_candidates_use_explicit_heuristic_window_without_transcript():
    analysis = make_analysis_fixture(duration=45.0, scenes=[]).model_copy(update={"transcript": None})
    candidates = score_short_candidates(analysis, count=2)

    assert candidates
    assert all(item.reason == "heuristic-window" for item in candidates)
    assert [item.title for item in candidates] == [f"Short {index}" for index in range(1, len(candidates) + 1)]


def test_short_candidates_fall_back_when_scene_boundaries_do_not_form_a_window():
    analysis = make_analysis_fixture(duration=45.0, scenes=[0.0]).model_copy(update={"transcript": None})

    candidate = score_short_candidates(analysis, count=1)[0]

    assert candidate.reason == "heuristic-window"


def test_short_candidates_group_transcript_speech_around_scene_boundaries():
    analysis = make_analysis_fixture(
        duration=45.0,
        scenes=[0.0, 10.0, 20.0, 45.0],
    ).model_copy(
        update={
            "transcript": Transcript(
                regions=[SpeechRegion(start=12.0, end=13.0, text="evidence-backed speech")]
            )
        }
    )

    candidate = score_short_candidates(analysis, count=1)[0]

    assert (candidate.source_start, candidate.source_end, candidate.reason) == (7.5, 22.5, "transcript-window")
