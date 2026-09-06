# Architecture

P0 is a local pipeline: CLI -> analysis -> validated project/timeline -> deterministic planner -> local FFmpeg renderer -> QA evidence. `project.json` and `timeline.json` are versioned Pydantic contracts with unknown-field rejection. Analysis, caches, profiles, captions, planners, renderer, and QA are separate modules with local tests.

The CLI validates file paths and schemas before work. Analysis cache identity combines a source SHA-256, canonical config fingerprint, and actual local FFmpeg/ffprobe version/build output, Python runtime, and optional transcription runtime versions. Rendering never re-runs analysis; it loads the structured project, verifies source durations and audio availability from a source-hash-matching persisted artifact or `ffprobe`, validates the timeline, and emits FFmpeg argv without a shell. Media stages and exclusive publication use the selected destination parent, including an explicitly requested output outside the project. Caption artifacts use a controlled temporary directory and are cleaned up.

Initialization preflights the complete metadata/render destination set and rejects occupied project artifacts. New metadata and renders use atomic exclusive publication; ordinary structured timeline editing remains an explicit replacement operation. Relative source references are contained within the manifest directory; explicit absolute local sources remain supported. QA distinguishes verified expectations, actual local content measurements, unavailable evidence, and failed invariants.

P0 authority is local filesystem state and validated contracts. P1/P2 remote providers, asset indexing, faceless assembly, advertising workflows, publishing, and telemetry are outside this architecture.
