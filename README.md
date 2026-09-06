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
videoos render input.videoos/project.json --dry-run
videoos render input.videoos/project.json
videoos qa input.videoos/renders/input.mp4 --timeline input.videoos/timeline.json
```

See [CLI reference](docs/CLI.md), [project format](docs/PROJECT_FORMAT.md), and [rendering](docs/RENDERING.md) for exact behavior. `render` consumes the existing project and timeline; it does not run analysis again.

## Capabilities and fallbacks

P0 supports local analysis, silence/scene-based talking-head planning, optional local `faster-whisper` transcription, structured timelines, FFmpeg rendering, Shorts candidates, and QA evidence. `doctor` reports optional availability; missing optional speech, scene, CV, Node, Blender, or VideoToolbox support is reported rather than silently substituted.

Faceless production, advertising generation, asset indexing, remote vision/audio providers, and upload/publish workflows are P1/P2 interfaces only. They are not implemented in P0. See [roadmap](docs/ROADMAP.md).

## Safety boundary

VideoOS executes local tools with argument arrays (`shell=False`), accepts structured inputs through validated schemas, writes atomically, confines renderer staging/output paths, and sends no telemetry. Review source-media licensing and FFmpeg redistribution obligations before distributing a bundled product; see [license audit](docs/LICENSE_AUDIT.md).
