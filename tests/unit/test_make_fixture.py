import subprocess

import pytest

from scripts.make_fixture import make_fixture


def test_make_fixture_reports_bounded_stdout_and_stderr_on_ffmpeg_failure(tmp_path, monkeypatch):
    """Catches fixture failures that hide FFmpeg stdout or unbounded stream output."""
    stdout = "o" * 513
    stderr = "e" * 513

    def fail(command, **kwargs):
        raise subprocess.CalledProcessError(1, command, output=stdout, stderr=stderr)

    monkeypatch.setattr("scripts.make_fixture.subprocess.run", fail)

    with pytest.raises(RuntimeError) as error:
        make_fixture(tmp_path / "fixture.mp4")

    message = str(error.value)
    assert stdout[:512] in message
    assert stderr[:512] in message
    assert stdout not in message
    assert stderr not in message
