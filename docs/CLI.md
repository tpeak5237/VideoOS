# CLI reference

All commands operate locally. `--help` is the authoritative runtime help.

| Command | Implemented P0 flags |
| --- | --- |
| `videoos doctor` | `--json` |
| `videoos analyze INPUT` | `--output PATH`, `--cache-dir PATH`, `--transcribe`, `--profile PROFILE`, `--json` |
| `videoos edit INPUT` | `--profile PROFILE`, `--aspect-ratio W:H`, `--resolution WIDTHxHEIGHT`, `--output PATH`, `--transcribe`, `--no-captions`, `--dry-run` |
| `videoos shorts INPUT` | `--count INTEGER` (minimum 1), `--output-dir PATH`, `--transcribe` |
| `videoos render PROJECT_JSON` | `--output PATH`, `--dry-run` |
| `videoos qa OUTPUT` | `--timeline PATH`, `--json` |

`doctor` exits 2 when `ffmpeg` or `ffprobe` is absent. `analyze` defaults to `INPUT.analysis.json`; its `--profile` validates a policy but does not apply it to analysis. `edit` defaults to `generic`, `16:9`, and `1920x1080`; it creates a project and normally renders/QA-checks it. `--dry-run` constructs no media output. `shorts` writes candidates even if FFmpeg is unavailable; renders are conditional on FFmpeg. `render` uses existing structured inputs only. `qa` writes a sibling `.qa.json` and exits nonzero on failed checks.
