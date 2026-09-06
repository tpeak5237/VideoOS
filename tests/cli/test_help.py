import json

from typer.testing import CliRunner

from videoos.cli import app

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
