# VideoOS P0 local verification record

**Recorded:** 2026-09-06T22:42:07+07:00
**Branch:** `feat/videoos-universal-editor`
**Environment:** macOS arm64; Python 3.12.13; Ruff 0.16.6; FFmpeg 9.0.1; ffprobe 9.0.1. Commands used `.venv/bin/python`, `.venv/bin/videoos`, and `PYTHONPATH=src` where importing the checkout was required.

## Evidence status

| Layer | Status | Evidence and limit |
| --- | --- | --- |
| IMPLEMENTED | IMPLEMENTED | Versioned project/timeline/analysis/QA contracts, local CLI, FFmpeg argv renderer, safe staged publication, and atomic JSON persistence exist in this checkout. |
| TESTED | TESTED | Fresh local Ruff, complete pytest, integration pytest, CLI smoke, ffprobe inspection, and artifact checks passed below. |
| DEPLOYED | BLOCKED / UNVERIFIED — no deployment target in scope | This P0 repository has no deployment artifact, target identity, staging environment, or release record to inspect. |
| VERIFIED LIVE | BLOCKED / UNVERIFIED — no deployment target in scope | Local synthetic-media execution is not deployed or live-workflow evidence. |

## Automated gates

Run from the repository root at 2026-09-06T22:42:07+07:00:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/ruff check .
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest -m integration tests/integration -q
git diff --check
```

Results:

```text
All checks passed!
133 passed in 1.83s
3 passed in 1.62s
```

## Local CLI smoke evidence

The following commands were run against a generated local source. All completed with exit code 0 after the two smoke-path repairs noted in the Task 12 report.

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/videoos --help
PYTHONDONTWRITEBYTECODE=1 .venv/bin/videoos doctor --json
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/make_fixture.py /tmp/videoos-fixture.mp4
PYTHONDONTWRITEBYTECODE=1 .venv/bin/videoos analyze /tmp/videoos-fixture.mp4 --json
PYTHONDONTWRITEBYTECODE=1 .venv/bin/videoos edit /tmp/videoos-fixture.mp4 --profile talking-head-shortform
PYTHONDONTWRITEBYTECODE=1 .venv/bin/videoos render /tmp/videoos-fixture.videoos/project.json --dry-run
PYTHONDONTWRITEBYTECODE=1 .venv/bin/videoos qa /tmp/videoos-fixture.videoos/renders/videoos-fixture.mp4 --json
PYTHONDONTWRITEBYTECODE=1 .venv/bin/videoos qa /tmp/videoos-fixture.videoos/renders/videoos-fixture.mp4 --timeline /tmp/videoos-fixture.videoos/timeline.json --json
```

`doctor --json` reported required `ffmpeg` and `ffprobe` available. Optional `faster_whisper`, `cv2`, `mediapipe`, and `blender` were unavailable; the workflow continued with the documented local fallbacks. `analyze` produced a four-second `640x360` artifact with two scenes, two silence regions, no transcription, and no warnings. `edit` produced a project, timeline, copied analysis, render, and passing QA report. The dry run reported `dry_run: true`, a structured plan with its FFmpeg argv array and operations, and did not change the rendered output SHA-256.

## Generated artifacts inspected

| Artifact | Canonical path | Result |
| --- | --- | --- |
| Source fixture | `/private/tmp/videoos-fixture.mp4` | SHA-256 `55b23f917a1bf92a5424f85b902d2cab30567e0db353d2dd8095e88b54ab2b01`; size `42206`; mtime remained `1788709195` across analyze, edit, dry-run, and QA. |
| Standalone analysis | `/private/tmp/videoos-fixture.mp4.analysis.json` | Created by `analyze`; source hash matches the fixture. |
| Project manifest | `/private/tmp/videoos-fixture.videoos/project.json` | Valid JSON; source ID and analysis reference SHA-256 match the source fixture. |
| Timeline | `/private/tmp/videoos-fixture.videoos/timeline.json` | Valid JSON; all timestamp fields inspected as finite. |
| Project analysis | `/private/tmp/videoos-fixture.videoos/analysis/55b23f917a1bf92a5424f85b902d2cab30567e0db353d2dd8095e88b54ab2b01.json` | Valid JSON; source hash matches the manifest and source. |
| Render | `/private/tmp/videoos-fixture.videoos/renders/videoos-fixture.mp4` | SHA-256 `c9940a33ecc39ac0a8ca84327b39b50e37737774706e6f6b54ca21663a569fe7` before and after dry-run. |
| QA report | `/private/tmp/videoos-fixture.videoos/renders/videoos-fixture.qa.json` | Valid JSON; `passed: true`; no sibling atomic-write temporary file remained. |

## Reproducible local artifact inspection

The following checks were run locally at `2026-09-06T22:54:37+07:00`. They are `TESTED` evidence for the listed generated fixture only; they do not establish `DEPLOYED` or `VERIFIED LIVE` status.

```sh
export PYTHONDONTWRITEBYTECODE=1
printf 'source_before '
shasum -a 256 /tmp/videoos-fixture.mp4
stat -f 'source_before mtime=%m size=%z' /tmp/videoos-fixture.mp4
.venv/bin/videoos render /tmp/videoos-fixture.videoos/project.json --dry-run
.venv/bin/videoos qa /tmp/videoos-fixture.videoos/renders/videoos-fixture.mp4 --timeline /tmp/videoos-fixture.videoos/timeline.json --json
printf 'source_after '
shasum -a 256 /tmp/videoos-fixture.mp4
stat -f 'source_after mtime=%m size=%z' /tmp/videoos-fixture.mp4
```

Observed result:

```text
source_before 55b23f917a1bf92a5424f85b902d2cab30567e0db353d2dd8095e88b54ab2b01  /tmp/videoos-fixture.mp4
source_before mtime=1788709195 size=42206
render: dry_run=True; warnings=[]; structured argv/operations plan emitted
qa: passed=true; 14 checks passed; warnings=[]
source_after 55b23f917a1bf92a5424f85b902d2cab30567e0db353d2dd8095e88b54ab2b01  /tmp/videoos-fixture.mp4
source_after mtime=1788709195 size=42206
```

The source fixture hash, mtime, and size were unchanged by dry-run and QA. The dry-run did not publish an output; QA regenerated only its sibling QA evidence file.

The following read-only Python command verifies strict JSON parsing, the versioned Pydantic model for each artifact, and that every numeric value in each JSON tree is finite:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python - <<'PY'
import json
import math
from pathlib import Path

from videoos.analysis.models import AnalysisArtifact
from videoos.core.io import load_model
from videoos.core.models import ProjectManifest, Timeline
from videoos.qa.models import QAReport

project_dir = Path('/private/tmp/videoos-fixture.videoos')
artifacts = {
    'project': (project_dir / 'project.json', ProjectManifest),
    'timeline': (project_dir / 'timeline.json', Timeline),
    'analysis': (next((project_dir / 'analysis').glob('*.json')), AnalysisArtifact),
    'qa': (project_dir / 'renders' / 'videoos-fixture.qa.json', QAReport),
}

def finite_violations(value, path='$'):
    if isinstance(value, dict):
        return [issue for key, item in value.items() for issue in finite_violations(item, f'{path}.{key}')]
    if isinstance(value, list):
        return [issue for index, item in enumerate(value) for issue in finite_violations(item, f'{path}[{index}]')]
    if isinstance(value, (int, float)) and not isinstance(value, bool) and not math.isfinite(value):
        return [path]
    return []

for name, (artifact_path, model_type) in artifacts.items():
    payload = json.loads(artifact_path.read_text(encoding='utf-8'))
    model = load_model(artifact_path, model_type)
    violations = finite_violations(payload)
    print(
        f'{name}: json_parse=ok model={type(model).__name__} model_validation=ok '
        f'finite_value_violations={violations}'
    )
PY
```

Observed result:

```text
project: json_parse=ok model=ProjectManifest model_validation=ok finite_value_violations=[]
timeline: json_parse=ok model=Timeline model_validation=ok finite_value_violations=[]
analysis: json_parse=ok model=AnalysisArtifact model_validation=ok finite_value_violations=[]
qa: json_parse=ok model=QAReport model_validation=ok finite_value_violations=[]
```

The following local scans inspect persisted artifacts only. The FFmpeg argument vector shown by `render --dry-run` is CLI output, not a shell command or a persisted project value.

```sh
if rg -n -i '(api[_-]?key|secret|password|authorization|bearer|/bin/(ba)?sh|shell[[:space:]]*=)' /tmp/videoos-fixture.videoos/project.json /tmp/videoos-fixture.videoos/timeline.json /tmp/videoos-fixture.videoos/analysis/*.json /tmp/videoos-fixture.videoos/renders/*.qa.json; then
  printf 'artifact_safety_scan=matches_found\n'
  exit 1
fi
printf 'artifact_safety_scan=no_secret_or_shell_text_matches\n'
if find /tmp/videoos-fixture.videoos/renders -maxdepth 1 -name '.videoos-fixture.qa.json.*.tmp' -print | grep -q .; then
  printf 'qa_temp_file_check=temporary_file_left_behind\n'
  exit 1
fi
printf 'qa_temp_file_check=no_temporary_file_left_behind\n'
```

Observed result:

```text
artifact_safety_scan=no_secret_or_shell_text_matches
qa_temp_file_check=no_temporary_file_left_behind
```

Inspection commands:

```sh
ffprobe -v error -print_format json -show_format -show_streams /tmp/videoos-fixture.videoos/renders/videoos-fixture.mp4
```

ffprobe found an H.264 video stream and AAC stereo audio stream in an MP4 container. The video is `1920x1080`, sample aspect ratio `1:1`, display aspect ratio `16:9`, with a `2.733333` second container duration. QA passed output existence, nonzero size, duration tolerance, video/audio stream presence, resolution, black-frame, audio-peak, finite source-duration, bounds, overlap, continuity, and caption-bound checks.

A read-only JSON inspection verified finite timestamps in `project.json`, `timeline.json`, analysis JSON, and QA JSON. A read-only artifact scan found no matches for secret-bearing terms or shell-command indicators (`api_key`, `secret`, `password`, `authorization`, `bearer`, `/bin/sh`, `/bin/bash`, or `shell =`). The visible dry-run plan is an FFmpeg argument vector, not a shell command, and is not persisted into a project artifact.

## Evidence boundaries

This record proves only the stated local checkout and generated local files at the timestamp above. It does not prove CI execution, deployment identity, a hosted runtime, authenticated provider behavior, source media supplied by a user, telemetry, backups, or a production/live workflow.
