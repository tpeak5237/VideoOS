import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.integration


def test_fixture_script_creates_requested_media(tmp_path):
    """The documented fixture command writes the requested local MP4."""
    output = tmp_path / "fixture.mp4"

    completed = subprocess.run(
        [sys.executable, "scripts/make_fixture.py", str(output)],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )

    assert completed.returncode == 0, completed.stderr
    assert output.is_file()
    assert output.stat().st_size > 0
