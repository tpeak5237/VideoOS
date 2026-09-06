"""Exercise the actual local subprocess safety and resource boundary."""

import json
import sys

import pytest

from videoos.analysis.runner import CommandRunner
from videoos.core.errors import ExternalCommandError


def test_runner_passes_argument_array_without_shell(tmp_path):
    marker = tmp_path / "must-not-exist"
    argument = f"$(touch {marker});'quoted' ไทย"
    result = CommandRunner().run([sys.executable, "-c", "import json,sys; print(json.dumps(sys.argv[1:]))", argument])
    assert json.loads(result.stdout) == [argument]
    assert not marker.exists()


def test_nonzero_command_raises_typed_error_with_bounded_stderr():
    with pytest.raises(ExternalCommandError, match="exit code 1") as caught:
        CommandRunner().run([sys.executable, "-c", "import sys; sys.stderr.write('bad media'*1000); sys.exit(1)"])
    assert len(str(caught.value)) < 1000


def test_missing_command_raises_typed_error():
    with pytest.raises(ExternalCommandError, match="not found"):
        CommandRunner().run(["/nonexistent/videoos-tool"])


def test_timed_out_command_raises_typed_error():
    with pytest.raises(ExternalCommandError, match="timed out"):
        CommandRunner(default_timeout=0.05).run([sys.executable, "-c", "import time; time.sleep(10)"])


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_output_limit_terminates_instead_of_truncating_evidence(stream):
    with pytest.raises(ExternalCommandError, match="output limit"):
        CommandRunner(max_output_bytes=1024).run([sys.executable, "-c", f"import sys; sys.{stream}.write('x'*1000000)"])
