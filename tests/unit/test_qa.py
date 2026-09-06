import json
from pathlib import Path

from tests.unit.factories import make_media_probe, make_timeline_with_caption
from videoos.analysis.models import MediaProbe
from videoos.core.models import SourceSegment, Timeline, Track
from videoos.qa.checks import check_output, check_timeline
from videoos.qa.models import QACheck, QAExpectation, QAReport
from videoos.qa.service import write_qa_report


def test_qa_flags_caption_outside_timeline():
    """Catches accepting a caption whose end exceeds the rendered timeline."""
    timeline = make_timeline_with_caption(start=0, end=10, cue_start=9, cue_end=11)

    checks = check_timeline(timeline, {"main": 10})

    assert any(check.status == "fail" and "caption" in check.name for check in checks)


def test_qa_accepts_matching_video_audio_output(tmp_path: Path):
    """Catches rejecting a present output whose required media invariants match."""
    output = tmp_path / "out.mp4"
    output.write_bytes(b"rendered")

    checks = check_output(
        output,
        QAExpectation(duration=4.0, width=1080, height=1920, audio_required=True),
        make_media_probe(),
    )

    assert all(check.status != "fail" for check in checks)


def test_report_serializes_passed_and_warnings(tmp_path: Path):
    """Catches omitting pass state or warning text from the persisted QA artifact."""
    report = QAReport(
        passed=True, duration=4.0, resolution="1080x1920", warnings=["scene fallback"]
    )
    destination = tmp_path / "output.qa.json"

    write_qa_report(destination, report)

    assert destination.exists()
    assert json.loads(destination.read_text(encoding="utf-8"))["passed"] is True


def test_timeline_reports_source_bounds_overlap_and_continuous_track_gap():
    """Catches treating source overflow, overlaps, and required-track gaps as valid."""
    timeline = Timeline(
        tracks=[
            Track(
                id="video",
                kind="video",
                segments=[
                    SourceSegment(source_id="main", source_start=0, source_end=4, timeline_start=0),
                    SourceSegment(source_id="main", source_start=4, source_end=11, timeline_start=3),
                    SourceSegment(source_id="main", source_start=0, source_end=1, timeline_start=8),
                ],
            ),
            Track(
                id="video-gap",
                kind="video",
                segments=[
                    SourceSegment(source_id="main", source_start=0, source_end=1, timeline_start=0),
                    SourceSegment(source_id="main", source_start=1, source_end=2, timeline_start=3),
                ],
            ),
        ]
    )

    checks = check_timeline(timeline, {"main": 10})

    assert {check.name for check in checks if check.status == "fail"} >= {
        "timeline.source_bounds",
        "timeline.track_overlaps",
        "timeline.track_gaps",
    }


def test_output_reports_missing_streams_and_nonfinite_duration(tmp_path: Path):
    """Catches passing a non-finite, video-less output when video and audio are required."""
    output = tmp_path / "out.mp4"
    output.write_bytes(b"rendered")
    probe = MediaProbe(duration=float("nan"), video=None, audio=None)

    checks = check_output(output, QAExpectation(duration=4.0, audio_required=True), probe)

    assert {check.name for check in checks if check.status == "fail"} >= {
        "output.duration",
        "output.video_stream",
        "output.audio_stream",
    }


def test_output_reports_missing_or_empty_file_as_failed_invariants(tmp_path: Path):
    """Catches treating a missing or zero-byte render as an acceptable output."""
    missing = check_output(tmp_path / "missing.mp4", QAExpectation(duration=4.0), make_media_probe())
    empty = tmp_path / "empty.mp4"
    empty.touch()
    zero_size = check_output(empty, QAExpectation(duration=4.0), make_media_probe())

    assert {check.name for check in missing if check.status == "fail"} >= {
        "output.exists",
        "output.nonzero_size",
    }
    assert any(check.name == "output.nonzero_size" and check.status == "fail" for check in zero_size)


def test_output_warns_for_black_frames_and_audio_peak_without_failing(tmp_path: Path):
    """Catches escalating advisory black-frame and peak detections into invariant failures."""
    output = tmp_path / "out.mp4"
    output.write_bytes(b"rendered")

    checks = check_output(
        output,
        QAExpectation(
            duration=4.0,
            black_frame_at_start=True,
            black_frame_at_end=True,
            audio_peak_dbfs=-0.5,
        ),
        make_media_probe(),
    )

    assert {check.name for check in checks if check.status == "warn"} == {
        "output.black_frame_start",
        "output.black_frame_end",
        "output.audio_peak",
    }
    assert all(check.status != "fail" for check in checks)


def test_report_is_not_passed_when_an_invariant_fails():
    """Catches caller-provided pass state overriding failed invariant checks."""
    report = QAReport(
        passed=True,
        checks=[QACheck(name="output.exists", status="fail", message="output is missing")],
    )

    assert report.passed is False


def test_report_uses_stable_sibling_qa_json_path(tmp_path: Path):
    """Catches nondeterministic output-report paths and key ordering."""
    report = QAReport(passed=True, duration=4.0, resolution="1080x1920")
    output = tmp_path / "output.mp4"

    write_qa_report(output, report)

    destination = tmp_path / "output.qa.json"
    assert destination.read_text(encoding="utf-8") == (
        '{\n  "checks": [],\n  "duration": 4.0,\n  "passed": true,\n'
        '  "resolution": "1080x1920",\n  "warnings": []\n}\n'
    )
