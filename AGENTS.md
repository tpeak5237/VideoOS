# VideoOS agent guide

## Scope and workspace

Work only on the checked-out feature branch/worktree. Do not modify `main`, deploy, push, upload media, introduce secrets or telemetry, or mutate source media. Preserve unrelated dirty changes. Before commits, inspect `git status --short --branch`; stage only owned paths.

## Trust boundaries

Treat CLI paths and JSON/YAML as untrusted. Do not build shell strings or use shell interpolation: local process execution must receive an argument sequence and use `shell=False`. Do not turn user content into FFmpeg filter text without an explicit validated renderer feature. No network upload is part of the P0 contract.

## Project files

- `project.json`: versioned `ProjectManifest`; declares project identity, immutable source references, target, and analysis references.
- `timeline.json`: versioned editable `Timeline`; declares tracks, source segments, captions, and removed ranges.
- `analysis/<sha256>.json`: local analysis evidence. It is an input to planning and cache validation, not a hand-edited rendering command.
- `renders/*.mp4` and `*.qa.json`: generated local output/evidence; never use a source path as a destination.

Schemas reject unknown fields. `render` validates segment source IDs, bounds, same-track overlaps, and caption bounds before generating local FFmpeg argv.

## Cache identity

Analysis is content-addressed from the source SHA-256 plus canonical analysis-config and tool-version fingerprints. A project analysis reference is reusable only when all three fingerprints match. A legacy `cache_key` is intentionally not reusable. Do not hand-edit a cache identity to force reuse.

## Safe edit workflow

1. Run `videoos edit INPUT ...` once to create a project, or open an existing project.
2. Copy `timeline.json` before changing it.
3. Edit only structured timeline fields: add/reorder non-overlapping segments, adjust source/timeline timestamps, captions, and supported transform/audio fields.
4. Preserve source IDs from `project.json`; ensure each `source_end` is within the source and every caption ends within timeline duration.
5. Select a fresh `OUTPUT` path. Run `videoos render PROJECT_JSON --output OUTPUT --dry-run`, then `videoos render PROJECT_JSON --output OUTPUT`, then `videoos qa OUTPUT --timeline timeline.json`. P0 supports one continuous video track; gaps, multiple tracks, and standalone audio tracks are rejected.

Agents edit structured timelines and rerender. They do not patch generated FFmpeg argv or ask users to execute ad-hoc FFmpeg commands.

## Verification

Use the project interpreter and source layout:

```sh
PYTHONPATH=src .venv/bin/python -m pytest tests/unit -q
PYTHONPATH=src .venv/bin/python -m pytest tests/integration -q
.venv/bin/ruff check src tests
git diff --check
```

Integration verification is local only; it is not CI, deployment, or live proof.
