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

`doctor` exits 2 when `ffmpeg` or `ffprobe` is absent. `analyze` defaults to `INPUT.analysis.json`; its `--profile` validates a policy but does not apply it to analysis. `edit` defaults to `generic`, `16:9`, and `1920x1080`; specifying only a named aspect derives its matching resolution (9:16 → 1080x1920, 4:5 → 1080x1350, 1:1 → 1080x1080). Explicit dimensions must be even and match the ratio. `--dry-run` constructs no media output. `shorts` requires FFmpeg and ffprobe for analysis and local rendering; it cannot create candidates without those tools. `render` uses existing structured inputs only.

`edit`, `render`, and `shorts` persist post-render QA and exit 1 on failed invariants; warnings remain nonfatal. Initialization refuses existing project artifacts, and rendering requires a fresh output and QA destination. `qa` writes a sibling `.qa.json` even for an unreadable container and exits nonzero on failed checks. With `--timeline`, a sibling `project.json` provides verified source bounds/audio expectations; without that context those checks are unavailable warnings. It never derives source duration from segment ends.
