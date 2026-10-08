# Maintenance verification · October 8, 2026

Target: existing public VideoOS baseline `0428fa0f35a662ad017db74afce9052ce3d96500`, branch `codex/videoos-verification-ci`. Local environment: macOS arm64, Python 3.12.13, FFmpeg/ffprobe 9.0.1. The installed FFmpeg build enables GPL and is an external executable, not a redistributed project artifact.

| Check actually run | Local result |
| --- | --- |
| `uv venv --python 3.12 .venv` | Passed |
| `uv pip compile pyproject.toml --extra dev --universal --generate-hashes --output-file requirements-dev.lock` | Hashed universal lock generated |
| `uv pip sync --python .venv/bin/python --require-hashes requirements-dev.lock` | Passed |
| `uv pip install --python .venv/bin/python --no-deps --no-build-isolation .` | Passed |
| `PYTHONPATH=src .venv/bin/python -m pytest tests/unit tests/cli -q` | 162 passed on locked pytest 9.1.1 |
| `PYTHONPATH=src .venv/bin/python -m pytest tests/integration -q` | 19 passed, including real media workflows and installed-wheel execution |
| `.venv/bin/ruff check src tests` | Passed |
| `.venv/bin/python -m build --no-isolation` | Source distribution and wheel built successfully |
| `.venv/bin/videoos doctor --json` | Exit 0; FFmpeg/ffprobe present |
| `uvx --python 3.12 pip-audit --require-hashes -r requirements-dev.lock` | No known vulnerabilities found in locked dependencies |
| `git diff --check` | Passed |

The original pytest 8.4.2 development dependency had PYSEC-2026-1845. The dev bound is now pytest >=9.0.3,<10 and the lock resolves 9.1.1. A fresh `pip-audit --path .venv/lib/python3.12/site-packages` reports no known third-party vulnerabilities; local `videoos` is skipped because it is not a PyPI package. This audit does not inspect local project source.

These tests used generated synthetic media. No original or user media was uploaded or changed. Optional faster-whisper, OpenCV, MediaPipe and Blender were unavailable; this run does not establish their behavior. The doctor observed VideoToolbox availability, which does not prove a successful hardware encode.

The first GitHub CI run on PR #2 passed the lock audit, lint and 162 unit/CLI tests but failed the offline installed-wheel integration: the unhashed resolver lacked registry metadata in its fresh cache. The test now installs the hashed lock offline into its isolated target and installs the wheel with `--no-deps`, while retaining package-resource, entrypoint and real-render assertions. It also includes the README referenced by package metadata and reports installation stderr on failure.

A new temporary virtual environment and an initially empty uv cache were populated using only the hashed lock; all 181 tests passed there. CI reruns independently on Ubuntu/Python 3.12 with FFmpeg and fonts. See [PR #2](https://github.com/tpeak5237/VideoOS/pull/2) for the actual current check result. No package registry or application deployment is performed.

VideoOS still has no project-level license. Passing tests or public visibility do not resolve redistribution rights or establish production readiness. Existing historical verification documentation is retained separately.
