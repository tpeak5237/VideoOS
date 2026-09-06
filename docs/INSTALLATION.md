# Installation

Install Python 3.12+ and local `ffmpeg`/`ffprobe`. On macOS with Homebrew: `brew install ffmpeg`. Then run `./scripts/bootstrap.sh --venv`, activate `.venv`, and run `videoos doctor`.

The script only creates/uses `.venv` when `--venv` is passed, installs `.[dev]` there, and never writes shell startup files or system-wide configuration. Without `--venv`, it only checks prerequisites. Optional extras are `videoos[speech]` for `faster-whisper` and `videoos[scenes]` for PySceneDetect/OpenCV.
