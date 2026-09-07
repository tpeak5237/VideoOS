# Troubleshooting

- `doctor` exits 2: install local `ffmpeg` and `ffprobe` (macOS/Homebrew: `brew install ffmpeg`) and rerun `videoos doctor --json`.
- Transcription unavailable: install `videoos[speech]` and use `--transcribe`; P0 otherwise records unavailable transcription rather than uploading media.
- Scene/CV capability unavailable: install `videoos[scenes]`; inspect `doctor` before expecting optional behavior.
- Render validation fails: restore the backup, then check source IDs, source bounds, same-track overlap, and caption duration in `timeline.json`; use `--dry-run` before a real render.
- Output/path error: do not use the source as an output and keep output beneath the project/renders location.
- Cache was not reused: do not edit fingerprints; a source, config, or tool-version change intentionally produces a new cache identity.
