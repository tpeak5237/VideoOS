# VideoOS final whole-branch fix report

Date: 2026-09-06. Branch: `feat/videoos-universal-editor`.
Starting commit: `7c540487ce91640c9c053a85a81f71b0c5225a13`.
Delivery: one local fix-wave commit containing this report; no push, merge, deployment, source-media upload, or subagents.

## Result and scope

C1 and I1–I12 have been addressed within the local P0 contract. Fresh verification passed **181 tests: 146 unit, 16 CLI, and 19 integration**, with no skips in these runs. Ruff passed both the source/tests scope and the entire checkout; `git diff --check` passed.

This does not establish complete implementation of every original design item or production readiness. Native caption burn-in cannot execute with this machine's FFmpeg because its `subtitles` filter is absent. The implemented CLI now rejects that request explicitly before rendering; controlled Unicode ASS serialization and its connection to the renderer are tested separately. Unsupported timeline composition is explicitly rejected. Remaining design-contract omissions are recorded in `docs/ROADMAP.md`.

The approved spec, plan, ledger, and final review were read first. Graph discovery returned “project not found or not indexed” for VideoOS, so direct source reads were used. The existing branch had no tracked changes, only pre-existing untracked bytecode directories. Those directories were preserved and are excluded from the commit.

## Findings addressed

| Finding | Change | Covering evidence |
| --- | --- | --- |
| C1 — destructive initialization | Preflight project metadata, reserved artifact directories, media output, and QA output before initialization. Reject existing artifacts and collisions with sources. Shorts preflights its metadata and candidate project directories. New metadata uses exclusive atomic publication; atomic replacement is retained only for intentional structured edits. Render protects every manifest source and project metadata, and preflights its report destination. | Existing project/timeline/analysis preservation; actual MP4 named `timeline.json`; repeated edit with a saved user caption; occupied render/QA rejection before analysis; repeated Shorts preservation; exclusive publication against an occupied racing target. |
| I1 — omitted wheel resources | Declare built-in YAML package data and use `importlib.resources` traversal. | Build an ordinary wheel from a temporary source copy, install it and dependencies offline to a separate target, import all five profiles outside the repository, execute the installed entrypoint, and run installed edit → rerender → QA. |
| I2 — audio loss/ignored adjustments | Add optional `SourceRef.has_audio`, independent of `SourceSegment.audio`. Creation carries verified availability; render verifies it from source-matching analysis or ffprobe, overriding stale declarations. Render operations carry adjustments. Apply requested normalization, gain, and fades; normalize format to 48 kHz stereo and pad to segment duration. Mixed sources receive generated silence only where audio is absent. | Real audible manual timeline; −20 dB attenuation within 0.7 dB; decoded start/end fade attenuation; −25 LUFS within 1 LU; mixed audible/silent segments and four-second duration; Shorts retains AAC; absent-source adjustments never request nonexistent audio; stale manifest audio flag is overridden. |
| I3 — captions disconnected | Serialize validated cues into a managed UTF-8 ASS file and pass it as `caption_file`. Check the installed `subtitles` filter and reject unavailable burn-in, including dry runs. Controlled temporary paths keep output-directory punctuation outside the native subtitle parser. ASS override punctuation is rendered as visible fullwidth punctuation; generated line breaks are the only text escapes. | CLI managed-artifact test captures Unicode ASS passed into the actual plan compiler and confirms cleanup/no analysis. Text override/event-injection regression. Real FFmpeg capability test observes the unavailable-filter error and confirms no output. Native burn-in branch exists in the regression but was not executed on this build. |
| I4 — top-left crop | Planner leaves crop offsets unspecified for centered fallback. Explicit manual offsets keep their absolute scaled-pixel meaning. | Decoded center pixel of a portrait render is from the green middle band of a red/green/blue source. |
| I5 — zoom timing and scale | Replace fixed-fps `zoompan` with centered crop/scale preserving frame timestamps. Continue the explicit maximum-scale warning. | Distinct decoded pixel output and two-second duration/frame-rate preservation at 24, 30, and 60 fps. Existing rerender integration retains source/cache immutability checks and now checks the corrected zoom operation. |
| I6 — discarded track semantics | Require exactly one continuous video track from zero. Reject gaps, overlaps, empty segments, multiple tracks, standalone audio tracks, and unknown track kinds before FFmpeg. | Parameterized rejection tests; real continuous/reordered rendering and mixed embedded-audio workflows. No compositor claim. |
| I7 — unmeasured QA passes | Scan video via safe `blackdetect` and audio via safe `volumedetect`. Unavailable measurements remain warnings. Audio expectation comes from verified source availability. Check SAR/DAR when a target is known. Correct historical verification claims. | All-black source produces endpoint warnings; actual finite peak evidence is collected; missing expected audio fails; unmeasured or failed-filter checks do not pass; mismatched display ratio fails. |
| I8 — invented source durations | Use manifest/source-verified durations. A detached timeline has unavailable source-bound checks, never self-certified segment ends. | Actual CLI QA accepts reordered [1,2] then [0,1] against a two-second source; rejects [6,8]; reports detached source bounds as unavailable. |
| I9 — inconsistent post-render QA | Centralize post-render QA in `_render`, persist reports for edit/render/Shorts, and propagate invariant failures to exit 1. Advisory warnings remain nonfatal. A failed container probe persists a failed report. New post-render reports publish exclusively. | All three real media-producing CLI paths are exercised with injected failed QA invariants and retained failed reports. Normal workflows pass with warnings. Unreadable-container persistence regression. |
| I10 — constant tool identity | Query actual FFmpeg and ffprobe version/build output through the shared runner before cache lookup. Include Python/adapter identity and available transcription provider/runtime package versions. A caller fingerprint supplements actual identity instead of replacing it. | Service regression changes ffprobe version, observes a different fingerprint/cache address and fresh probe; identical calls still reuse analysis. Real installed-tool analysis runs in integration. |
| I11 — CWD-dependent sources | Canonicalize relative sources against the resolved manifest directory with containment checks; reject parent and symlink escapes. Preserve explicit absolute local references. Pass canonical paths through verification and rendering. | Unit parent/symlink rejection; actual render from another CWD containing a competing same-name silent source still uses the project's audible source. |
| I12 — inconsistent targets/display ratios | Require even H.264/yuv420p dimensions matching the declared ratio. Derive matching dimensions for the four named CLI aspects when resolution is omitted. Add `setsar=1` and probe SAR/DAR for QA. | Mismatched/odd dimensions reject before rendering; CLI portrait-only request derives 1080x1920; decoded portrait output reports exact square pixels/9:16; incorrect SAR fails QA. |

## Files changed

Core and orchestration:

- `src/videoos/cli.py`
- `src/videoos/core/models.py`
- `src/videoos/core/io.py`
- `src/videoos/core/paths.py`

Analysis, packaging, planning, captions, and rendering:

- `pyproject.toml`
- `src/videoos/profiles/loader.py`
- `src/videoos/analysis/models.py`
- `src/videoos/analysis/probe.py`
- `src/videoos/analysis/runner.py`
- `src/videoos/analysis/service.py`
- `src/videoos/planner/talking_head.py`
- `src/videoos/captions/serializers.py`
- `src/videoos/renderer/operations.py`
- `src/videoos/renderer/ffmpeg.py`

QA:

- `src/videoos/qa/models.py`
- `src/videoos/qa/checks.py`
- `src/videoos/qa/measurements.py` (new)
- `src/videoos/qa/service.py`

Tests:

- `tests/unit/factories.py`
- `tests/unit/test_final_fixes.py` (new)
- `tests/unit/test_analysis_service.py`
- `tests/unit/test_renderer.py`
- `tests/unit/test_captions.py`
- `tests/unit/test_qa.py`
- `tests/unit/test_runner.py`
- `tests/cli/test_commands.py`
- `tests/integration/test_final_media_regressions.py` (new)
- `tests/integration/test_installed_wheel.py` (new)
- `tests/integration/test_re_render.py`

Documentation and delivery:

- `AGENTS.md`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/CLI.md`
- `docs/PROJECT_FORMAT.md`
- `docs/RENDERING.md`
- `docs/ROADMAP.md`
- `docs/VERIFICATION.md`
- `.superpowers/sdd/2026-09-06-videoos-p0/progress.md`
- `.superpowers/sdd/2026-09-06-videoos-p0/final-fix-report.md` (this file)

The approved spec, original plan, and final review report remain unchanged.

## Commands and results

Executed from `/Users/theerapatp/Documents/ChatGPT/VideoOS` using Python 3.12.13, FFmpeg/ffprobe 9.0.1 (Homebrew macOS Apple Silicon build). The FFmpeg build enables libx264 and VideoToolbox but does not enable libass/subtitles.

Fresh final verification:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest -p no:cacheprovider tests/unit -q
# 146 passed in 0.34s

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest -p no:cacheprovider tests/cli -q
# 16 passed in 0.25s

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest -p no:cacheprovider tests/integration -q
# 19 passed in 8.83s

.venv/bin/ruff check --no-cache src tests
# All checks passed!

.venv/bin/ruff check --no-cache .
# All checks passed!

git diff --check
# Exit 0; no whitespace errors.
```

The suites above partition all repository tests; combined count is 181. Integration includes real local FFmpeg workflows, decoded pixels/PCM, installed-wheel execution, and the actual missing-subtitle-capability rejection. Its pass count does not imply native caption rendering occurred.

Additional investigation/verification commands:

```sh
git status --short --branch
git rev-parse HEAD
.venv/bin/python --version
ffmpeg -version
ffprobe -version
uv pip install --python .venv/bin/python --offline 'setuptools>=68'
```

The local test environment originally lacked setuptools; the offline installation added setuptools 84.0.0 so the declared build backend could run. No application dependency specification was changed for this environment preparation. The wheel test uses setuptools to build from a temporary copy, then `uv pip install --python <project interpreter> --offline --target <temporary installed directory> <wheel>` with normal dependencies. It removes the source-tree `PYTHONPATH`, asserts imports resolve into that installed directory, and runs the installed console script. Wheel/media artifacts stay in pytest-managed temporary directories, outside the checkout.

Focused regression commands were also run during development against `test_final_fixes.py`, `test_analysis_service.py`, `test_captions.py`, `test_runner.py`, `tests/cli/test_commands.py`, `test_installed_wheel.py`, and `test_final_media_regressions.py`. The initial boundary tests reproduced 13 failures. The wheel test reproduced missing built-in profiles after its build prerequisite was supplied. The service test reproduced unchanged fingerprints after a simulated ffprobe upgrade. The ASS text test reproduced retained override syntax. The added container test reproduced missing failed-report persistence. Each was rerun after its fix; the fresh suites above supersede intermediate results. Real zoom/audio failures were also established by the supplied final review, then covered by the new decoded regressions.

## Self-review and minor findings

- Reviewed the changed publication paths, CLI→metadata→renderer→QA flow, stream expectation propagation, source path resolution, filter construction, cache identity, and failure exit paths against the approved spec and final review.
- Preserved the existing real integration suite and its source/cache/no-reanalysis assertions. Replaced obsolete assertions for the defective `zoompan` expression with the corrected operation, backed by spatial/frame-rate tests.
- Added all four VideoToolbox enablement/capability combinations. Actual hardware encoding is not claimed.
- Corrected README/agent rerender examples to use a fresh output, architecture output-location wording, and Shorts/FFmpeg requirements.
- External processes now default to a 3600-second execution limit, 16 MiB per captured stream, and a 128 KiB argument bound. Time/output limits are configurable through documented environment variables. A limit violation terminates the process group and raises a typed error, so partial diagnostic output cannot become successful analysis/QA evidence. Shell execution remains disabled.
- Recorded migration registry, persisted style/profile provenance, overlays/transitions/composition, and configurable export preset registry omissions explicitly in ROADMAP. Also retained the minor render-JSON and broader primitive-coverage follow-ups.
- Self-review caught the unreadable-container persistence edge case and added a covering test/fix before final verification. Post-render QA reports now use exclusive publication as well.
- No independent new reviewer or subagent was used, as instructed. No source media was edited; real-media tests generate and inspect disposable local fixtures and include byte-for-byte source/project preservation assertions.

## Evidence limits

| Layer | Status |
| --- | --- |
| IMPLEMENTED | Listed fixes, explicit rejections, resource limits, and documentation exist on the requested feature branch. Full original design alignment is not claimed; deferrals are listed above and in ROADMAP. |
| TESTED | 181 fresh passing local tests, including 19 integration tests; Ruff and whitespace checks pass. The installed-wheel local editing workflow executes outside the source tree. |
| DEPLOYED | BLOCKED / UNVERIFIED — no deployment target in scope. Nothing pushed, merged, or deployed. |
| VERIFIED LIVE | BLOCKED / UNVERIFIED — no deployment target in scope. Synthetic local media is not live-user evidence. |
| BLOCKED / UNVERIFIED | Native ASS/subtitle rendering and Thai font/glyph coverage on a libass-enabled build; actual Whisper inference/provider models; actual VideoToolbox encoding; CI; other OS/FFmpeg builds; transitive redistribution audit and commercial operations. |

Caption rejection is intentional on this machine. Obtaining native caption evidence requires a capability-equipped FFmpeg/font installation; this wave did not modify system FFmpeg or download a speech model. Per-segment normalization precedes gain/fades, so those explicit adjustments can change final integrated loudness. In-process optional provider inference is not covered by external-process limits. Unsupported track composition is rejected instead of approximated. Low-level render callers must supply verified source audio availability; CLI orchestration performs verification for old and new manifests.

The final commit is intended to contain only the files listed above. Existing untracked bytecode remains outside the commit. The feature branch/workspace is retained for the user's next review.
