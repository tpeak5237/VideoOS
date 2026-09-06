#!/usr/bin/env sh
set -eu

usage() {
  printf '%s\n' "Usage: ./scripts/bootstrap.sh [--venv]"
  printf '%s\n' "  --venv  Create/use .venv and install the local development extra."
}

create_venv=false
case "${1:-}" in
  "") ;;
  --venv) create_venv=true ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac

python_bin="${PYTHON:-python3}"
if ! command -v "$python_bin" >/dev/null 2>&1; then
  printf '%s\n' "Python 3.12+ is required; set PYTHON to its executable." >&2
  exit 2
fi

if ! "$python_bin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'; then
  printf '%s\n' "Python 3.12+ is required." >&2
  exit 2
fi

for binary in ffmpeg ffprobe; do
  if command -v "$binary" >/dev/null 2>&1; then
    printf '%s found: %s\n' "$binary" "$(command -v "$binary")"
  else
    printf '%s\n' "$binary is missing. macOS/Homebrew hint: brew install ffmpeg" >&2
  fi
done

if [ "$create_venv" = true ]; then
  "$python_bin" -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install '.[dev]'
  printf '%s\n' "Installed VideoOS development dependencies in .venv."
else
  printf '%s\n' "Diagnostics complete. Run ./scripts/bootstrap.sh --venv to create a project-local environment and install .[dev]."
fi
