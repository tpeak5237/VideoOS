# VideoOS

VideoOS is a local, non-destructive video-editing CLI. P0 analyzes a local source, writes a versioned project and timeline, and renders through local FFmpeg. It does not upload media or replace the source file.

## Install

Requirements: Python 3.12+, `ffmpeg`, and `ffprobe` on `PATH`.

```sh
./scripts/bootstrap.sh --venv
source .venv/bin/activate
videoos doctor
```

On macOS, the bootstrap diagnostic suggests `brew install ffmpeg` when either required executable is absent. It never changes shell profiles or other system-wide configuration.

## First video (P0)

Use a local MP4; paths are passed as arguments, not interpolated into shell commands.

```sh
videoos doctor
videoos analyze ./input.mp4 --profile generic
videoos edit ./input.mp4 --profile talking-head-shortform --aspect-ratio 9:16 --resolution 1080x1920
```

`analyze` writes `./input.mp4.analysis.json` by default and stores reusable local analysis under `./.videoos-cache/`. `edit` writes `input.videoos/project.json`, `input.videoos/timeline.json`, an `analysis/` artifact, a render under `renders/`, and (after a non-dry render) a sibling `.qa.json` report. The original MP4 is never an output target.

## Safe timeline edit and rerender (P0)

Edit structured data, not an FFmpeg command. Back up `timeline.json`, keep every `source_id` declared in `project.json`, keep same-track segments non-overlapping, ensure `source_end` stays within the source, and keep captions within the assembled timeline duration. Then validate the plan before rendering:

```sh
cp input.videoos/timeline.json input.videoos/timeline.before-edit.json
# Edit input.videoos/timeline.json with a JSON-aware editor.
videoos render input.videoos/project.json --output input.videoos/renders/revised.mp4 --dry-run
videoos render input.videoos/project.json --output input.videoos/renders/revised.mp4
videoos qa input.videoos/renders/revised.mp4 --timeline input.videoos/timeline.json
```

See [CLI reference](docs/CLI.md), [project format](docs/PROJECT_FORMAT.md), and [rendering](docs/RENDERING.md) for exact behavior. `render` consumes the existing project and timeline; it does not run analysis again.

Project initialization is exclusive: repeated `edit`/`shorts` commands reject existing artifacts. Use `render` with a fresh output name for timeline edits. P0 renders one continuous video track; gaps, multiple tracks, and standalone audio tracks are rejected. Every media-producing command writes QA and exits nonzero on failed invariants; advisory warnings remain nonfatal.

## Capabilities and fallbacks

P0 supports local analysis, silence/scene-based talking-head planning, optional local `faster-whisper` transcription, structured timelines, FFmpeg rendering, Shorts candidates, and QA evidence. `doctor` reports optional availability; missing optional speech, scene, CV, Node, Blender, or VideoToolbox support is reported rather than silently substituted.

Faceless production, advertising generation, asset indexing, remote vision/audio providers, and upload/publish workflows are P1/P2 interfaces only. They are not implemented in P0. See [roadmap](docs/ROADMAP.md).

## Safety boundary

VideoOS executes local tools with argument arrays (`shell=False`), accepts structured inputs through validated schemas, writes atomically, confines renderer staging/output paths, and sends no telemetry. Review source-media licensing and FFmpeg redistribution obligations before distributing a bundled product; see [license audit](docs/LICENSE_AUDIT.md).


## Development and verification

See [CONTRIBUTING.md](CONTRIBUTING.md) for a clean environment and the exact unit/CLI, FFmpeg integration, Ruff and Python package build commands. [GitHub CI](.github/workflows/ci.yml) provisions Python 3.12, uv, FFmpeg and fonts and exercises the installed wheel as well as source imports. CI configuration is not evidence that a hosted run has passed.

[Current local verification](docs/MAINTENANCE_VERIFICATION.md), [security boundaries](SECURITY.md) and [maintenance decisions](docs/DECISIONS.md) explain local artifact handling, optional capabilities and the distinction between local tests and release proof.

## Project license status

This publicly visible repository currently has **no project-level license**. It must not be described as legally open source solely because its source is public. Reuse and redistribution rights require a separate ownership/license decision. Dependency licenses and media/FFmpeg obligations are recorded in [the license audit](docs/LICENSE_AUDIT.md); they do not grant a license to VideoOS itself.
