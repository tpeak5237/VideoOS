import json

from typer.testing import CliRunner

from videoos.cli import _doctor_capabilities, app
from videoos.core.errors import ExternalCommandError

runner = CliRunner()


def test_help_lists_core_commands():
    """Removing a registered core command must break the public CLI contract."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("doctor", "analyze", "edit", "shorts", "render", "qa"):
        assert command in result.stdout


def test_doctor_json_is_machine_readable():
    """Breaking structured doctor output must be caught without asserting terminal formatting."""
    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code in (0, 2)
    payload = json.loads(result.stdout)
    assert payload["command"] == "doctor"
    assert set(payload["capabilities"]) >= {"ffmpeg", "ffprobe", "faster_whisper"}


def test_doctor_marks_encoder_unavailable_when_typed_runner_fails(monkeypatch):
    """An encoder-inspection failure must not change required binary capability reporting."""

    class FailingRunner:
        def run(self, _: list[str]):
            raise ExternalCommandError("ffmpeg encoder inspection failed")

    monkeypatch.setattr(
        "videoos.cli.shutil.which",
        lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None,
    )

    capabilities = _doctor_capabilities(runner=FailingRunner())

    assert capabilities["ffmpeg"] == {"available": True, "required": True}
    assert capabilities["ffprobe"] == {"available": False, "required": True}
    assert capabilities["h264_videotoolbox"] == {"available": False, "required": False}
