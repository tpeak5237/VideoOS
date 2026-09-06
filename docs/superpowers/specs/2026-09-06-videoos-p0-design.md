# VideoOS P0 Design

**Date:** 2026-09-06  
**Status:** Approved design  
**Branch:** `feat/videoos-universal-editor`

## Purpose

VideoOS is a local-first, CLI-first video editing system that turns media analysis and explicit editing decisions into deterministic, non-destructive renders. The first implementation milestone is a complete P0 vertical slice: a user can analyze a source, generate an explainable edit plan, validate it, render a new output with FFmpeg, and inspect automated QA results without requiring a paid API or uploading media.

The system is intentionally modular. P0 must be useful on its own while exposing stable contracts for optional speech, vision, asset-search, motion-graphics, and alternate-renderer integrations.

## Scope and non-goals

### P0 scope

- Python 3.12+ package and `videoos` CLI.
- Versioned Pydantic project and timeline schemas.
- Source hashing and cached analysis artifacts.
- `ffprobe` metadata analysis.
- FFmpeg silence analysis with a deterministic fallback when audio is absent.
- Optional scene detection and optional local transcription adapters.
- Profile-driven talking-head edit planning.
- Deterministic source trimming, concatenation, audio normalization, and crop/reframe fallback.
- SRT, VTT, and ASS caption generation when transcript data is available.
- Safe FFmpeg command construction using subprocess argument arrays.
- Output QA for container, duration, streams, resolution, timeline/caption bounds, and warnings.
- `doctor`, `analyze`, `edit`, `render`, `qa`, and `shorts` CLI surfaces sufficient for the first workflows.
- Tiny synthetic-media fixtures and automated unit/integration/smoke tests.
- Installation, architecture, project-format, profile, rendering, troubleshooting, license, and roadmap documentation.

### Follow-on scope

P1 adds face detection/tracking, smoother subject-aware reframing, vlog and podcast profiles, local asset indexing, semantic retrieval, faceless assembly, advertising grammar, brand kits, motion templates, and richer QA. P2 adds Motion Canvas, Blender, diarization, OpenCut interchange, and richer semantic planning.

The first milestone does not build a desktop timeline UI, hosted service, paid inference integration, or distributed processing architecture. These may consume the core services later but are not prerequisites for local CLI editing.

## Architecture

The package lives under `src/videoos/` and is organized by responsibility:

```text
src/videoos/
├── core/        # schemas, time math, validation, paths, errors
├── analysis/    # ffprobe, silence, scenes, cache, artifact models
├── speech/      # transcription protocol and local provider adapters
├── captions/    # cue creation and SRT/VTT/ASS serialization
├── profiles/    # editable profile loading and built-in defaults
├── planner/     # explainable deterministic edit decisions
├── renderer/    # render operations and FFmpeg argv generation
├── qa/          # output inspection and QA report models
├── assets/      # future metadata index and P1 search adapters
├── integrations/ # optional Motion Canvas, Blender, OpenCut seams
└── cli.py       # thin command orchestration
```

The dependency direction is inward: CLI depends on application services; application services depend on protocols and core models; adapters depend on external tools and implement protocols. Core models never import FFmpeg, a model SDK, or UI code.

The normal P0 data flow is:

```text
source file
  → SHA-256 + tool/config fingerprint
  → cached AnalysisArtifact
  → profile + planner
  → validated Timeline
  → Renderer (FFmpeg argv)
  → output file + QAReport
```

Analysis and planning are separate from rendering. Rerendering a modified `timeline.json` uses the existing timeline and does not re-run Whisper, scene detection, or other analysis unless the source or analysis configuration changed.

## Project and timeline format

Projects are non-destructive and portable:

```text
project/
├── sources/
├── analysis/
├── cache/
├── renders/
├── project.json
└── timeline.json
```

`project.json` contains `version`, project identity, source references, target export settings, style/profile/brand selections, and provenance. `timeline.json` contains a validated `Timeline` only; it never contains arbitrary AI prose or shell commands.

The initial schema includes:

- `ProjectManifest`, `ProjectInfo`, `InputFile`, `TargetSpec`, and `StyleSpec`.
- `MediaAsset` and `AnalysisArtifact` with source hash, duration, dimensions, frame rate, codecs, audio streams, orientation, silence regions, scene boundaries, speech/transcript references, and warnings.
- `Timeline`, `Track`, and ordered `Segment` records.
- Source segments with source/timeline ranges, semantic role, reason, confidence, crop/reframe, conservative zoom, and audio adjustments.
- Caption cues, text overlays, transition records, and export metadata.
- Explicit schema version and a migration registry seam. Unsupported future versions fail clearly.

Validation rejects negative, non-finite, or reversed timestamps; source ranges outside known media duration; overlaps within a track; invalid aspect ratios/resolutions; captions outside the rendered timeline; and unsafe path references. Timestamp math uses a single normalized internal representation and tolerates neither NaN nor infinity.

Every automatic decision should be auditable. A silence removal records its source range, reason, and confidence; a future semantic short candidate records its score and evidence. The renderer consumes these records as operations, not natural-language instructions.

## Analysis and cache

`videoos analyze input.mp4` resolves the input path, computes a source hash, calls `ffprobe` once for metadata, and stores a JSON analysis artifact beneath a cache directory such as `.videoos/cache/<source-hash>/`. The cache key also includes the analysis configuration and tool versions so incompatible results are not silently reused.

Required analysis is metadata and audio-safe silence detection. Scene detection, transcription, face analysis, and embeddings are provider protocols with capability/status fields. Missing optional providers result in warnings and a usable partial artifact. Malformed media, missing required binaries, unreadable paths, and timeout/non-zero subprocess exits produce actionable typed errors.

The analysis API should be injectable so tests can use a fake `ProbeRunner`, deterministic fixture artifacts, or a real FFmpeg installation without changing planner behavior.

## Profiles and planning

Profiles are user-editable YAML or JSON. Built-in profiles include at least `generic`, `talking-head-shortform`, `talking-head-longform`, `vlog`, and `podcast` definitions, with P0 behavior implemented for the talking-head defaults. Profile fields control silence removal, maximum pause, caption settings, reframe behavior, zoom interval, shot preference, and audio targets.

The planner is deterministic for the same source analysis, profile, and planner version. It creates keep/remove decisions from speech/silence regions, preserves natural breathing with bounded pauses, applies conservative cuts, adds crop/reframe operations based on target aspect ratio, adds captions from available transcript cues, and adds audio normalization. Random zoom spam and opaque semantic guesses are prohibited. Decisions include reason and confidence where meaningful.

`videoos shorts source.mp4 --count N` uses the same analysis and timeline contracts. The first implementation may score candidate speech windows heuristically from transcript/speech density and boundaries; each candidate must include source range, score, title/hook suggestion when available, and reason. It must gracefully report that semantic shorts are unavailable when no transcript backend exists rather than inventing content.

## Rendering

The renderer accepts only a validated `Timeline` and explicit export settings. It compiles the timeline into FFmpeg operations for trimming, concatenation, scaling, cropping, audio filters, caption files, overlays, and output encoding. The command builder returns an argv list and a structured operation trace. It never joins user-controlled values into a shell string or invokes a shell.

Rendering writes a new file under `renders/` or an explicit validated output path. Source media remains untouched. Temporary concat lists, subtitle files, and intermediate artifacts live in a managed temporary directory and are cleaned up after success or failure. `--dry-run` prints the planned operations and argv in a redacted, readable form without creating the final render.

Export presets are configurable rather than scattered across platform conditionals. Initial presets cover YouTube 16:9, Shorts/Reels/TikTok 9:16, Instagram 4:5, and square 1:1, with H.264/AAC defaults and optional VideoToolbox selection when available.

Caption serialization uses Unicode-safe text and sensible line breaking. Burn-in uses generated files and controlled filter arguments; subtitle text is escaped for the selected format. Caption timing is validated before FFmpeg is invoked.

## QA and failure handling

`videoos qa output.mp4` and post-render QA create `output.qa.json`. Checks include output existence, readable container, duration, resolution, video stream, audio stream when expected, invalid timestamps, timeline gaps/overlaps, caption bounds, and basic black-frame/audio-peak warnings where detectable. A QA warning is distinct from a failed invariant.

Optional capability failure is explicit:

- no Whisper backend: keep scene/silence editing, omit semantic speech cuts/captions, and report the limitation;
- no scene detector: continue with metadata/audio-only planning;
- no vision backend: use weighted center crop fallback;
- no Motion Canvas or Blender: use FFmpeg/basic overlay paths.

Required failure is fail-fast with a non-zero CLI exit and a safe message that does not expose secrets or raw command internals unnecessarily. JSON output modes remain machine-readable.

## Security and privacy

All source media, filenames, subtitle text, and manifest paths are untrusted. Paths are resolved and checked against the project/output policy; traversal and unexpected absolute references are rejected where the command does not explicitly permit them. FFmpeg and ffprobe receive argv arrays, not shell commands. Subprocesses have bounded arguments, captured output, and configured timeouts where practical.

VideoOS does not upload media, emit telemetry, or call network services by default. Optional network-capable adapters must be opt-in, documented, and isolated from the local core. Secrets are never written into manifests, logs, QA reports, or dry-run output. Error handling avoids reflecting unsafe filter strings or arbitrary paths without escaping.

## Testing strategy

Unit tests cover:

- Pydantic schema validation and version handling;
- timestamp math, aspect ratios, and range clipping;
- profile parsing and default resolution;
- silence-to-cut planning;
- caption segmentation and SRT/VTT/ASS output;
- FFmpeg argv generation and path escaping;
- cache-key determinism;
- shorts candidate scoring and asset metadata lookup seams.

Integration tests generate tiny synthetic media with FFmpeg and verify analyze, simple edit, crop/reframe, caption burn-in, concatenation, audio normalization, render, and QA. Tests that need an unavailable optional provider are marked as explicit capability skips; core tests do not silently substitute a fake for a real FFmpeg integration.

CLI smoke tests exercise `videoos --help`, `videoos doctor`, `videoos analyze <fixture>`, `videoos edit <fixture>`, `videoos render <generated-project>`, and `videoos qa <output>`. Verification records exact commands and distinguishes local test evidence from deployment or live evidence; this repository has no deployment target in the P0 scope.

## Documentation and delivery

The repository will include `README.md`, `AGENTS.md`, and the requested docs under `docs/`, including architecture, installation, CLI, project format, profiles, rendering, advertising/faceless placeholders with accurate scope, troubleshooting, license audit, and roadmap. `AGENTS.md` will describe safe agent edits, cache behavior, timeline manipulation, test commands, and the rule that agents modify structured timelines rather than generated FFmpeg commands.

Major milestones will be committed coherently on `feat/videoos-universal-editor`; `main` will not be modified, merged, or deployed. The initial commit will contain this approved spec, followed by implementation commits for core/schema, analysis, renderer/QA, profiles/CLI, tests, and documentation.

## Success criteria

The P0 milestone is successful when a fresh local checkout with documented dependencies can:

1. analyze a tiny MP4 and produce a cached artifact;
2. create and validate a structured timeline with explainable edits;
3. render a new file with reduced silence, valid encoding, normalized audio, and optional captions when transcript data exists;
4. re-edit `timeline.json` and rerender predictably without reanalysis;
5. generate a machine-readable QA report;
6. pass the automated unit/integration/CLI checks available in the local environment.

P1/P2 capabilities will be labeled by their implementation and test evidence. No source code, build, screenshot, or local test result will be presented as deployed or live-verified proof.
