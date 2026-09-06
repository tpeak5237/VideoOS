# Architecture

P0 is a local pipeline: CLI -> analysis -> validated project/timeline -> deterministic planner -> local FFmpeg renderer -> QA evidence. `project.json` and `timeline.json` are versioned Pydantic contracts with unknown-field rejection. Analysis, caches, profiles, captions, planners, renderer, and QA are separate modules with local tests.

The CLI validates file paths and schemas before work. Analysis cache identity combines a source SHA-256, canonical config fingerprint, and tool fingerprint. Rendering never re-runs analysis; it loads the structured project, verifies source durations from a valid persisted artifact or `ffprobe`, validates the timeline, and emits FFmpeg argv without a shell. Staged outputs are confined to the destination project directory and published atomically.

P0 authority is local filesystem state and validated contracts. P1/P2 remote providers, asset indexing, faceless assembly, advertising workflows, publishing, and telemetry are outside this architecture.
