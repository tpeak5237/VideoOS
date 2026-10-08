# Contributing to VideoOS

Read [AGENTS.md](AGENTS.md), [architecture](docs/ARCHITECTURE.md), [project format](docs/PROJECT_FORMAT.md) and [CLI reference](docs/CLI.md) before changing the local pipeline. Work on a feature branch, preserve source media and unrelated changes, and keep outputs in fresh destinations.

## Reproduce verification

Use Python 3.12+, FFmpeg/ffprobe and `uv`. The installed-wheel integration test invokes `uv` offline. Syncing the hashed lock first supplies its package archives; the test installs those exact locked dependencies into an isolated target before installing the wheel without re-resolving dependencies.

```sh
uv venv --python 3.12 .venv
uv pip sync --python .venv/bin/python --require-hashes requirements-dev.lock
uv pip install --python .venv/bin/python --no-deps --no-build-isolation .
PYTHONPATH=src .venv/bin/python -m pytest tests/unit tests/cli -q
PYTHONPATH=src .venv/bin/python -m pytest tests/integration -q
.venv/bin/ruff check src tests
.venv/bin/python -m build --no-isolation
.venv/bin/videoos doctor --json
uvx --python 3.12 pip-audit --require-hashes -r requirements-dev.lock
git diff --check
```

Integration tests create synthetic media in temporary directories and use real local FFmpeg. Missing executables may skip tests; a skipped test is not a pass. Optional speech inference, subtitle/font support and hardware encoders require their own capability evidence. CI uses Ubuntu with Python 3.12, uv, FFmpeg and local fonts; it does not upload media or deploy an application.

## Dependency lock maintenance

`requirements-dev.lock` pins the base runtime, testing and build tools across supported platforms with package hashes. Optional speech/scenes providers remain separate and are not installed or verified by this lock. Refresh deliberately with `uv pip compile pyproject.toml --extra dev --universal --generate-hashes --output-file requirements-dev.lock`, inspect the diff, rerun tests/build and audit the result. CI installs the locked tools and builds without isolation so setuptools is not silently re-resolved.

## Change and review boundaries

Use subprocess argument arrays with `shell=False`. Treat paths, structured manifests and timeline fields as untrusted. Preserve schema rejection, source/output collision protection, fresh artifact publication, cache identity and measured QA. Never hand-edit generated FFmpeg commands or silently substitute unavailable optional providers.

Fixtures and issue attachments must be synthetic or explicitly licensed and free of sensitive content. Do not commit original media, generated renders, local analysis/cache artifacts, credentials or private configuration. Describe behavior, tests actually run and unverified capabilities in each pull request.

## License status

This public repository currently has no project-level license. Public visibility alone does not grant open-source reuse or redistribution rights. Dependency notices do not license VideoOS itself. Maintainers must resolve project ownership and choose a license separately before describing it as legally open source. Do not add third-party media, models or fonts without verifying their terms.
