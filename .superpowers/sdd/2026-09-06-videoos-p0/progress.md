# SDD ledger — plan: docs/superpowers/plans/2026-09-06-videoos-p0.md

## Setup

- Spec read: `docs/superpowers/specs/2026-09-06-videoos-p0-design.md`.
- Plan read: `docs/superpowers/plans/2026-09-06-videoos-p0.md`.
- Branch: `feat/videoos-universal-editor`.
- Branch base before implementation: `dda4575`.
- Working tree was clean before execution.

## Preflight scan

### Shared-file and shared-interface rows

| Tasks | Shared surface | Finding | Ruling |
|---|---|---|---|
| 1 ↔ 2 | `core/time.py`, `core/errors.py`, `pyproject.toml`; `TimeRange` and typed errors | Task 2 consumes the primitives created by Task 1; no contradiction. | Task 1 owns primitive behavior; Task 2 uses it through imports. |
| 1 ↔ 10 | `pyproject.toml` | Task 10 adds the pytest integration marker after Task 1 creates package metadata; additive change. | Preserve Task 1 dependency bounds and add only marker configuration. |
| 2 ↔ 3 | `core/models.py` vs `analysis/models.py`; Pydantic persistence | Separate model namespaces; no file conflict. | Keep shared timeline models in core and media-probe/artifact models in analysis. |
| 2 ↔ 4 | `analysis/models.py` references core range/model types | Task 4 extends analysis models after Task 3 creates `MediaProbe`; no contradiction. | Add artifact types without moving `MediaProbe` out of analysis. |
| 2 ↔ 5 | `CaptionCue` is shared by core and caption serializers | Plan explicitly makes `CaptionCue` a core model and `CaptionStyle` a captions model. | Captions depend inward on core; do not duplicate `CaptionCue`. |
| 2 ↔ 6 | `Timeline`, `TargetSpec`, `TimeRange`, test factories | Planner consumes the validated schema; no contradiction. | Factories are test-only and must not become runtime dependencies. |
| 2 ↔ 7 | `ProjectManifest`, `Timeline`, `SourceSegment` | Renderer consumes validated models; no contradiction. | Renderer validates and refuses to accept raw dictionaries. |
| 2 ↔ 8 | `Timeline`, captions, `TargetSpec` | QA checks the same model invariants; no contradiction. | QA reports failures instead of mutating timelines. |
| 2 ↔ 9 | `load_model`, `save_model_atomic`, manifest/timeline files | CLI orchestrates core persistence; no contradiction. | CLI uses the shared atomic IO functions only. |
| 3 ↔ 4 | `analysis/models.py`, `CommandRunner`, `MediaProbe` | Task 3 creates probe primitives and Task 4 extends the analysis model; planned order is valid. | Task 4 modifies, not replaces, `MediaProbe`. |
| 3 ↔ 7 | `CommandRunner`, media metadata | Renderer reuses safe subprocess behavior; no contradiction. | Renderer receives/injects the runner; no second shell execution path. |
| 3 ↔ 9 | `probe_media`, command errors | CLI maps typed errors to exit codes; no contradiction. | Keep bounded stderr in errors and safe user-facing CLI messages. |
| 4 ↔ 5 | `Transcript`, `Transcriber`, `AnalysisService` | Analysis service accepts the provider protocol and stores transcript data; no contradiction. | Speech providers stay lazy and optional. |
| 4 ↔ 6 | `AnalysisArtifact`, silence/scenes | Planner consumes cached artifact fields; no contradiction. | Analysis remains side-effecting; planner remains deterministic/pure. |
| 4 ↔ 9 | `AnalysisService.analyze` | CLI invokes the service for analyze/edit/shorts; render must not invoke it. | Preserve the no-reanalysis render invariant. |
| 5 ↔ 6 | transcript words, caption cues, source-to-timeline mapping | Planner maps captions after cuts; no contradiction. | Clip/drop invalid cues before renderer invocation. |
| 5 ↔ 7 | serialized caption file and burn-in filter | Renderer consumes an explicitly generated caption file; no contradiction. | Escape only the controlled filter path and keep text in subtitle files. |
| 6 ↔ 7 | `Timeline`, `TargetSpec`, transforms | Renderer compiles planner output; no contradiction. | Renderer does not recalculate semantic decisions. |
| 6 ↔ 8 | timeline bounds and candidate metadata | QA can validate planner output; no contradiction. | Candidate metadata is separate from the render timeline. |
| 6 ↔ 9 | profile loader, talking-head/shorts planner | CLI passes explicit profile/target options; no contradiction. | Defaults resolve in one profile loader. |
| 7 ↔ 8 | render output and `QAReport` | Renderer produces output; QA probes it; no contradiction. | QA runs after successful render and reports warnings distinctly. |
| 7 ↔ 9 | `FfmpegRenderer.build_plan/render` | CLI passes manifest/timeline and dry-run; no contradiction. | CLI never builds FFmpeg strings directly. |
| 8 ↔ 9 | QA service and CLI `qa` command | CLI persists/prints the report; no contradiction. | Non-zero exit only for failed invariants. |
| 9 ↔ 10 | CLI app and end-to-end helpers | Integration tests exercise the public CLI; no contradiction. | Helpers assert and surface command output on failure. |
| 10 ↔ 11 | fixture policy and documentation commands | Tests and docs share no runtime code; no contradiction. | Never commit generated binary fixtures. |
| 11 ↔ 12 | `docs/ROADMAP.md`, verification record | Task 12 may update capability status after docs exist; additive. | Keep implementation/test evidence separate from deploy/live evidence. |

### Per-task self-consistency rows

| Task | Own-text check | Ruling |
|---|---|---|
| 1 | Tests cover version, path escape, and finite time; files/interfaces provide each symbol. | Proceed. Use `python3` until a local environment is created. |
| 2 | Tests cover version, range, overlap, evidence, and persistence; file map includes models, IO, and factories. | Proceed. |
| 3 | Tests cover shell flag, non-zero command, probe parsing, and cache; implementation steps define the same argv. | Proceed. |
| 4 | Parser/service tests align with artifact models, cache reuse, and explicit scene/silence fallback. | Proceed. |
| 5 | Tests cover transcript segmentation, SRT/VTT, and unavailable provider; interfaces add ASS and lazy provider behavior. | Proceed. |
| 6 | Profile, mapping, planner, and candidate tests align with deterministic outputs and declared model interfaces. | Proceed. Test helpers will define `make_analysis_fixture`. |
| 7 | Renderer tests cover argv/path escaping/dry-run; implementation branches audio vs video-only as specified. | Proceed. |
| 8 | QA tests cover timeline failure, matching output, and JSON report; check names/statuses align with models. | Proceed. |
| 9 | CLI tests cover help, missing input, and no-reanalysis; command list and handler steps match. | Proceed. |
| 10 | Integration tests exercise edit, QA, and rerender; helper file and fixture interface are defined. | Proceed. |
| 11 | Doc smoke tests check required files and fast-path commands; task creates them. | Proceed. |
| 12 | Verification commands and evidence labels match the spec and explicit no-deployment scope. | Proceed. |

## Rulings

- `Ruling: use python3/project-local interpreter for plan commands — the machine has no `python` executable, but `python3` is available and satisfies the runtime floor — cost if wrong: command examples may need a documented interpreter substitution.`

## Task checklist

### Task 1 review findings

- Important: `ensure_output_path` was check-then-use and did not provide an atomic/non-following output creation boundary. Fix round 1 will add and test a safe exclusive publish/reservation API for the later renderer to consume.
- Minor (deferred): add broader direct coverage for `ensure_output_path`, symlink containment, `seconds`, `TimeRange`, and the exception hierarchy if not covered by the scoped fix.
- Minor (deferred): the package entry point remains unusable until the planned CLI task creates `videoos.cli`; this is an intentional cross-task dependency.
- Task 1: fix round 1/5 (1 addressed, 0 open; commits `063f82c`..`728043f`).
- Task 1: complete (commits `063f82c`..`728043f`, review clean; 2 deferred minors).

- [x] Task 1: package foundation and safe primitives (commits `063f82c`..`728043f`, review clean)
### Task 2 review findings

- Important: `AnalysisRef` did not explicitly enforce source SHA-256 plus analysis configuration/tool fingerprint. Add validated identity fields and mismatch/reuse tests.
- Important: `Evidence.action`, `Evidence.reason`, and `SourceSegment.role` were unconstrained strings, allowing arbitrary prose or command-shaped decision records. Add closed vocabularies and bounded structured parameters while leaving caption text free-form.
- Important: `AudioAdjustment.gain_db` and `target_lufs` accepted non-finite JSON values. Add finite signed-range validators and reject non-standard JSON constants.
- Fix round 1 re-review: cache identity and non-finite audio handling were addressed; structured decision parameters still lacked upper bounds, and legacy version-1 `analysis.cache_key` manifests no longer loaded. Fix round 2 is required.
- Task 2: fix round 1/5 (3 addressed; 2 remaining findings carried into round 2; commits `1144b89`..`7a983d4`).
- Task 2: fix round 2/5 (2 addressed, 0 open; commit `7f37da8`).
- Task 2: complete (commits `1144b89`..`7f37da8`, review clean).
- [x] Task 2: versioned project and timeline schemas (commits `1144b89`..`7f37da8`, review clean)
### Task 3 review findings

- Important: `AnalysisCache.artifact_path` omitted the tool fingerprint even though `key_for` included it. Fix round 1 must make artifact addressing carry the complete cache identity and add a regression test.
- Task 3: fix round 1/5 (1 addressed, 0 open; commits `252d726`..`617b8ec`).
- Task 3: complete (commits `252d726`..`617b8ec`, review clean).
- [x] Task 3: safe runner, ffprobe, hashing, and cache (commits `252d726`..`617b8ec`, review clean)
### Task 4 review findings

- Important: an invalid `silence_start`/`silence_end` pair cleared pending state without producing the required unclosed-silence warning. Fix round 1 must clear pending state only for valid paired ends and add regression coverage.
- Task 4: fix round 1/5 (1 addressed, 0 open; commits `9e7b4ac`..`3619a45`).
- Task 4: complete (commits `9e7b4ac`..`3619a45`, review clean).
- [x] Task 4: analysis artifacts, silence, scenes, and service (commits `9e7b4ac`..`3619a45`, review clean)
### Task 5 review findings

- Important: a single word longer than `max_duration` bypassed duration enforcement. Fix round 1 must define and test an explicit overlong-word policy.
- Important: transcript input ordering was not validated, so serializers could emit descending cues. Fix round 1 must enforce chronological ordering or reject unsorted input with tests.
- Important: ASS style color fields accepted commas/newlines and could inject ASS structure. Fix round 1 must constrain color grammar and add injection-focused tests.
- Task 5: fix round 1/5 (3 addressed, 0 open; commits `56781e9`..`d725e60`).
- Task 5: complete (commits `56781e9`..`d725e60`, review clean; faster-whisper runtime remains unverified).
- [x] Task 5: speech protocol and caption engine (commits `56781e9`..`d725e60`, review clean)
### Task 6 review findings

- Critical: caption words spanning a cut were retained and emitted as continuous cues. Fix round 1 must detect cut intersection and discard or split/clip before segmentation, with single- and multi-cut tests.
- Important: center-crop decisions ignored quarter-turn display rotation. Fix round 1 must normalize display dimensions for crop decisions and add coverage.
- Minor (deferred): cut endpoints need an explicit half-open boundary convention and test.
- Task 6: fix round 1 re-review: rotation was addressed, but valid caption words touching cut boundaries were still dropped because source-to-timeline used inclusive cut membership. Fix round 2 must align mapping with the open-interval caption rule and test both boundary directions.
- Task 6: fix round 1/5 (1 Critical and 1 Important addressed; boundary minor carried into round 2; commits `d81cd15`..`befc0b7`).
- Task 6: fix round 2/5 (1 Critical addressed, 0 open; commit `b035e5a`).
- Task 6: complete (commits `d81cd15`..`b035e5a`, review clean; planner remains local-only).
- [x] Task 6: profiles, planner, and shorts candidates (commits `d81cd15`..`b035e5a`, review clean)
- [x] Task 7: FFmpeg renderer and dry-run compiler (commits `874c35a`, review clean; 1 deferred minor)

### Task 7 review findings

- Minor (deferred): add parameterized direct coverage for hardware enabled/disabled and VideoToolbox capability true/false. No Critical/Important findings.
- Task 7: complete (commit `874c35a`, review approved).
### Task 8 review findings

- Important: video-track gaps failed unconditionally. Add an explicit caller-controlled continuity expectation and fail gaps only when continuity is required.
- Important: `QAReport.passed` could become stale after a caller mutated the checks list. Derive pass state at serialization or make checks/pass state immutable/computed.
- Minor (deferred): add tests for explicit black-frame/audio-peak escalation settings.
- Task 8: fix round 1 re-review: continuity and escalation were addressed, but serialization forced `QAReport(passed=False)` with no failed checks to `passed: true`. Fix round 2 must preserve explicit false state while still reflecting appended failed checks.
- Task 8: fix round 1/5 (2 Important findings and minor escalation coverage addressed; commits `4f908ee`..`dfc01a6`).
- Task 8: fix round 2/5 (1 Important finding addressed, 0 open; commit `95e9783`).
- Task 8: complete (commits `4f908ee`..`95e9783`, review clean).
- [x] Task 8: output and timeline QA (commits `4f908ee`..`95e9783`, review clean)
### Task 9 review findings

- Important: `render` loaded schema-valid but semantically invalid timelines without calling `Timeline.validate_against_sources`. Fix round 1 must validate source bounds/overlaps/caption bounds against probed or persisted source durations and add reject-path tests.
- Important: `doctor` used direct `subprocess.run` for encoder inspection instead of the shared typed `CommandRunner`. Fix round 1 must route it through the runner and report encoder inspection failure as an unavailable optional capability.
- Task 9: fix round 1/5 (2 addressed, 0 open; commits `5ec65d7`..`b890270`).
- Task 9: complete (commits `5ec65d7`..`b890270`, review clean; successful media workflows remain unverified).
- [x] Task 9: CLI commands and orchestration (commits `5ec65d7`..`b890270`, review clean)
### Task 10 review findings

- Important: integration rerender used a fresh output path and did not prove occupied-target rejection/non-overwrite. Fix round 1 must add an occupied-output test that asserts bytes remain unchanged and the original render remains intact.
- Important: fixture-generation failure output discarded stdout and exposed only a fixed stderr prefix without a stated bounded policy. Fix round 1 must include both captured streams under an explicit bounded diagnostic policy.
- Task 10: fix round 1/5 (2 addressed, 0 open; commits `9a87b5b`..`73be033`).
- Task 10: complete (commits `9a87b5b`..`73be033`, review clean; local FFmpeg/ffprobe integration verified).
- [x] Task 10: synthetic fixtures and end-to-end verification (commits `9a87b5b`..`73be033`, review clean)
### Task 11 review findings

- Important: `docs/RENDERING.md` claimed outputs were confined to the project directory, but explicit `render --output PATH` accepts a validated destination parent outside it. Correct the documentation or enforce containment; preserve actual CLI behavior accurately.
- Important: `docs/LICENSE_AUDIT.md` omitted the declared build dependency `setuptools>=68`. Add a verified row with license/source/redistribution notes.
- Task 11: fix round 1/5 (2 Important findings addressed, 0 open; commit `95a9fcd`).
- Task 11: complete (commits `52c6a83`..`95a9fcd`, review clean; docs/unit/integration locally verified).
- [x] Task 11: documentation, examples, bootstrap, and license audit (commits `52c6a83`..`95a9fcd`, review clean)
### Task 12 review findings

- Important: `docs/VERIFICATION.md` claimed artifact hash/mtime, JSON-schema, finite-value, secret/shell-indicator, and temporary-file checks without recording exact commands/results. Fix round 1 must add reproducible inspection commands and outcomes.
- Task 12: fix round 1/5 (1 Important finding addressed, 0 open; commit `7c54048`).
- Task 12: complete (commits `559c605`..`7c54048`, review clean; local verification record complete).
- [x] Task 12: full local verification and evidence record (commits `559c605`..`7c54048`, review clean)

## Final whole-branch review findings

- Critical C1: `edit` can overwrite source media or existing project metadata/timeline edits before render-target collision checks. Preflight all generated paths and reject existing/colliding project artifacts before any write; apply to Shorts too.
- Important I1: built-in profile YAML files are absent from normal wheel/package installs. Package them and test a non-editable installed artifact.
- Important I2: renderer infers audio presence from optional adjustment fields, drops adjustment values, and Shorts can silently produce video-only output. Preserve verified audio-stream availability separately, apply gain/fades/LUFS, and handle mixed/absent audio explicitly.
- Important I3: CLI never serializes timeline captions or passes a caption file to the renderer; connect validated cues to controlled subtitle artifacts and report missing burn-in capability accurately.
- Important I4: planner crop metadata forces renderer crop offsets to `(0,0)`, producing top-left instead of centered crop. Align the coordinate convention and add spatial coverage.
- Important I5: zoompan changes duration and its expression does not apply requested zoom. Replace with timing-preserving zoom and spatial regression coverage across frame rates.
- Important I6: renderer discards `timeline_start`, track identity, gaps, overlaps, and standalone audio semantics. Implement them or reject unsupported layouts before rendering.
- Important I7: QA passes unmeasured black-frame/audio-peak checks and does not require audio when expected. Collect measurements or report unavailable, and propagate verified stream expectations.
- Important I8: CLI QA invents source durations from timeline segment ends. Use verified manifest/source durations; report source-bound verification unavailable without source context.
- Important I9: edit/render/Shorts do not consistently run and propagate post-render QA failures. Run QA after every media-producing command and return non-zero on failed invariants while retaining reports.
- Important I10: production cache config uses a constant tool fingerprint instead of actual installed tool/provider versions. Derive and inject real fingerprints.
- Important I11: relative manifest source paths resolve against caller CWD instead of the project manifest directory. Resolve project-relative references against the manifest directory with containment checks.
- Important I12: target aspect ratio/resolution/SAR validation is inconsistent and accepts unrealizable or mismatched values. Validate/derive consistent even dimensions, normalize SAR, and verify display ratio.
- Final review minors: add committed VideoToolbox parameterization, update rerender/architecture/Shorts docs, add execution/output bounds, and track remaining design-contract deferrals explicitly.

### Final fix wave

- [x] Whole-branch fix wave: C1/I1–I12 addressed in the local P0 scope; hardware gate/docs/process-bound minors handled and remaining design/coverage deferrals tracked in ROADMAP. Fresh verification: 146 unit + 16 CLI + 19 integration = 181 passing tests; Ruff (source/tests and whole checkout) and whitespace checks pass. Native subtitle burn-in remains unavailable on the installed FFmpeg; captioned renders explicitly reject it. No deployment/live claim, push, merge, or subagents. See `final-fix-report.md` for changed files, commands/results, self-review, and evidence limits. Delivered by the local commit containing this ledger entry.
