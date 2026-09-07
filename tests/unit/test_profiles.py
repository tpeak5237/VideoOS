from pathlib import Path

import pytest

from videoos.profiles.loader import load_profile


def test_builtin_profile_is_editable_and_has_conservative_zoom():
    profile = load_profile("talking-head-shortform")

    assert profile.silence.max_pause_ms == 350
    assert profile.zoom.max_scale <= 1.08
    assert profile.provenance.endswith("talking-head-shortform.yaml")


def test_profile_loader_accepts_user_yaml_and_rejects_unknown_required_field(tmp_path: Path):
    profile_path = tmp_path / "custom.yaml"
    profile_path.write_text(
        """
name: custom
silence: {remove: true, max_pause_ms: 400}
captions: {enabled: true, max_words_per_line: 4}
reframe: {subject_tracking: false}
zoom: {enabled: false, min_interval_seconds: 8, max_scale: 1.05}
audio: {speech_target_lufs: -16, music_under_speech_lufs: -28}
""".strip(),
        encoding="utf-8",
    )

    assert load_profile(str(profile_path)).provenance == str(profile_path.resolve())
    profile_path.write_text(profile_path.read_text(encoding="utf-8") + "\nzoon: {}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="zoon"):
        load_profile(str(profile_path))
