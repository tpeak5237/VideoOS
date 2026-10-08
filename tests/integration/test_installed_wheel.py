"""Exercise packaged resources from an installed wheel with no source-tree imports."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def test_installed_wheel_profiles_and_entrypoint(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    build = tmp_path / "build"
    build.mkdir()
    shutil.copyfile(repo / "pyproject.toml", build / "pyproject.toml")
    shutil.copyfile(repo / "README.md", build / "README.md")
    shutil.copytree(repo / "src", build / "src", ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    subprocess.run([sys.executable, "-c", "from setuptools.build_meta import build_wheel; build_wheel('dist')"], cwd=build, env=env, check=True, capture_output=True, timeout=60)
    installed = tmp_path / "installed"
    # Hashed installation caches package archives without necessarily caching the
    # unhashed registry metadata required by a new dependency resolution. Reuse
    # the audited lock offline, then install only the wheel being tested.
    dependencies = subprocess.run(
        ["uv", "pip", "sync", "--python", sys.executable, "--offline",
         "--require-hashes", "--target", str(installed), str(repo / "requirements-dev.lock")],
        cwd=tmp_path, env=env, capture_output=True, text=True, check=False, timeout=60,
    )
    assert dependencies.returncode == 0, dependencies.stdout + dependencies.stderr
    wheel = subprocess.run(
        ["uv", "pip", "install", "--python", sys.executable, "--offline", "--no-deps",
         "--target", str(installed), str(next((build / "dist").glob("*.whl")))],
        cwd=tmp_path, env=env, capture_output=True, text=True, check=False, timeout=60,
    )
    assert wheel.returncode == 0, wheel.stdout + wheel.stderr
    env["PYTHONPATH"] = str(installed)
    smoke = """
import videoos
from videoos.profiles.loader import load_profile
from typer.testing import CliRunner
from videoos.cli import app
assert 'installed' in videoos.__file__, videoos.__file__
for name in ('generic', 'talking-head-shortform', 'talking-head-longform', 'vlog', 'podcast'):
    assert load_profile(name).name == name
assert CliRunner().invoke(app, ['--help']).exit_code == 0
assert CliRunner().invoke(app, ['doctor', '--json']).exit_code == 0
from pathlib import Path
from videoos.analysis.runner import CommandRunner
CommandRunner().run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=green:s=160x90:r=24', '-t', '1', '-c:v', 'libx264', 'source.mp4'])
for args in (
    ['edit', 'source.mp4', '--output', 'project', '--resolution', '320x180'],
    ['render', 'project/project.json', '--output', 'project/renders/second.mp4'],
    ['qa', 'project/renders/second.mp4', '--timeline', 'project/timeline.json', '--json'],
):
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
assert Path('project/renders/second.qa.json').is_file()
"""
    result = subprocess.run([sys.executable, "-c", smoke], cwd=tmp_path, env=env, capture_output=True, text=True, check=False, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    entrypoint = subprocess.run([str(installed / "bin/videoos"), "--help"], cwd=tmp_path, env=env, capture_output=True, text=True, check=False, timeout=30)
    assert entrypoint.returncode == 0, entrypoint.stdout + entrypoint.stderr
