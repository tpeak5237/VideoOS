import subprocess

import pytest

from videoos.analysis.runner import CommandRunner
from videoos.core.errors import ExternalCommandError


def test_runner_passes_argument_array_without_shell(monkeypatch: pytest.MonkeyPatch):
    """Catches a regression that could turn media paths into shell syntax."""
    calls: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> object:
        calls.update(args=args, kwargs=kwargs)
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(subprocess, "run", fake_run)

    CommandRunner().run(["ffprobe", "-i", "file with spaces.mp4"])

    assert calls["args"] == (["ffprobe", "-i", "file with spaces.mp4"],)
    assert calls["kwargs"] == {
        "shell": False,
        "check": False,
        "capture_output": True,
        "text": True,
        "timeout": None,
    }


def test_nonzero_command_raises_typed_error_with_bounded_stderr(
    monkeypatch: pytest.MonkeyPatch,
):
    """Catches leaking an unbounded external-tool diagnostic on failure."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: type(
            "Result", (), {"returncode": 1, "stdout": "", "stderr": "bad media" * 1_000}
        )(),
    )

    with pytest.raises(ExternalCommandError, match="ffprobe.*exit code 1") as exc_info:
        CommandRunner().run(["ffprobe", "bad.mp4"])

    assert len(str(exc_info.value)) < 1_000


def test_missing_command_raises_typed_error(monkeypatch: pytest.MonkeyPatch):
    """Catches exposing a raw FileNotFoundError to analysis callers."""
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()))

    with pytest.raises(ExternalCommandError, match="ffprobe.*not found"):
        CommandRunner().run(["ffprobe", "clip.mp4"])


def test_timed_out_command_raises_typed_error(monkeypatch: pytest.MonkeyPatch):
    """Catches exposing a raw timeout exception to analysis callers."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            subprocess.TimeoutExpired(cmd=["ffprobe", "clip.mp4"], timeout=2, stderr="too slow")
        ),
    )

    with pytest.raises(ExternalCommandError, match="ffprobe.*timed out"):
        CommandRunner().run(["ffprobe", "clip.mp4"], timeout=2)
