# License audit

Audit date: 2026-09-06. This records direct declarations in `pyproject.toml`, not a complete transitive SBOM. Licenses were checked against package metadata and the linked official project sources on this date; verify the exact resolved versions and FFmpeg build before redistribution.

| Scope | Dependency / license | Purpose | Official source | Redistribution consideration |
| --- | --- | --- | --- | --- |
| Runtime | Pydantic / MIT | validated schemas | https://github.com/pydantic/pydantic | Preserve applicable MIT notice when redistributing. |
| Runtime | PyYAML / MIT | profile parsing | https://pyyaml.org/ | Preserve applicable MIT notice. |
| Runtime | Rich / MIT | terminal tables | https://github.com/Textualize/rich | Preserve applicable MIT notice. |
| Runtime | Typer / MIT | CLI | https://github.com/fastapi/typer | Preserve applicable MIT notice. |
| Optional `speech` | faster-whisper / MIT | local transcription adapter | https://github.com/SYSTRAN/faster-whisper | Optional; model weights and transitive runtimes have separate terms. |
| Optional `scenes` | PySceneDetect / BSD-3-Clause | scene detection | https://github.com/Breakthrough/PySceneDetect | Preserve BSD notice and disclaimer. |
| Optional `scenes` | opencv-python / Apache-2.0 | OpenCV binding extra | https://github.com/opencv/opencv-python | Preserve Apache-2.0 notices; native/transitive components may add notices. |
| Dev only | pytest / MIT | tests | https://github.com/pytest-dev/pytest | Not required by end users unless bundled. |
| Dev only | pytest-cov / MIT | coverage tests | https://github.com/pytest-dev/pytest-cov | Not required by end users unless bundled. |
| Dev only | Ruff / MIT | linting | https://github.com/astral-sh/ruff | Not required by end users unless bundled. |
| External executable | FFmpeg / LGPL-2.1-or-later by default upstream | local probing/rendering | https://ffmpeg.org/legal.html | The actual binary's configure flags govern obligations. GPL-enabled builds can impose GPL terms; do not represent a bundled binary as LGPL without inspecting that build and providing required notices/source/offer. |

VideoOS does not bundle FFmpeg or optional adapters by default. Future remote/asset/advertising adapters are disabled by default and require their own dependency, provider-term, privacy, and redistribution audit. Media rights are separate from software licenses; users must have rights to every input, model, font, caption, and output asset.
