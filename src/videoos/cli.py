"""Local, typed command orchestration for VideoOS.

The command layer validates untrusted CLI and structured-file inputs, then
delegates media work to the existing analysis, planning, rendering, and QA
modules. It never invokes a shell or uploads media.
"""

from __future__ import annotations

import importlib.util
import json
import platform
import shutil
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import typer
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from videoos.analysis.cache import sha256_file
from videoos.analysis.models import AnalysisArtifact, AnalysisConfig
from videoos.analysis.probe import probe_media
from videoos.analysis.runner import CommandRunner
from videoos.analysis.service import AnalysisService
from videoos.core.errors import (
    DependencyError,
    ExternalCommandError,
    UnsafePathError,
    ValidationError,
    VideoOSError,
)
from videoos.core.io import load_model, save_model_atomic
from videoos.core.models import (
    AnalysisRef,
    ProjectManifest,
    SourceRef,
    SourceSegment,
    TargetSpec,
    Timeline,
    Track,
)
from videoos.planner.shorts import ShortCandidate, score_short_candidates
from videoos.planner.talking_head import plan_talking_head
from videoos.profiles.loader import load_profile
from videoos.qa.checks import check_output, check_timeline
from videoos.qa.models import QAExpectation, QAReport
from videoos.qa.service import write_qa_report
from videoos.renderer.ffmpeg import FfmpegRenderer
from videoos.speech.faster_whisper import FasterWhisperTranscriber

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Local, non-destructive video editing.")
_CONSOLE = Console()
_OPTIONAL_MODULES = ("faster_whisper", "cv2", "mediapipe")


class _ShortMetadata(BaseModel):
    source_start: float
    source_end: float
    score: float
    reason: str
    title: str
    hook: str | None = None


class _ShortsArtifact(BaseModel):
    source: str
    candidates: list[_ShortMetadata]


class _UnavailableTranscriber:
    """An explicit provider that lets analysis record unavailable transcription."""

    def transcribe(self, _: Path) -> Any:
        raise DependencyError("faster-whisper is unavailable; install with: pip install 'videoos[speech]'")


def _json(payload: Mapping[str, Any]) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _table(command: str, payload: Mapping[str, Any]) -> None:
    table = Table(title=f"VideoOS {command}")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            rendered = str(value)
        table.add_row(key, rendered)
    _CONSOLE.print(table)


def _emit(command: str, payload: Mapping[str, Any], *, json_output: bool) -> None:
    envelope = {"command": command, **payload}
    if json_output:
        _json(envelope)
    else:
        _table(command, payload)


def _error(command: str, error: Exception, *, json_output: bool) -> None:
    message = str(error) or error.__class__.__name__
    payload = {"error": {"type": error.__class__.__name__, "message": message}}
    if json_output:
        _json({"command": command, **payload})
    else:
        typer.echo(f"error: {message}", err=True)


def _run(
    command: str,
    *,
    json_output: bool,
    operation: Callable[[], Mapping[str, Any]],
    failed: Callable[[Mapping[str, Any]], bool] | None = None,
) -> None:
    try:
        payload = operation()
    except (VideoOSError, FileNotFoundError, OSError, ValueError) as error:
        _error(command, error, json_output=json_output)
        raise typer.Exit(code=2) from error
    _emit(command, payload, json_output=json_output)
    if failed is not None and failed(payload):
        raise typer.Exit(code=1)


def _existing_file(value: Path, *, label: str) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.exists():
        raise ValidationError(f"{label} not found: {candidate}")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_file():
        raise ValidationError(f"{label} must be a regular file: {candidate}")
    return resolved


def _output_path(value: Path, *, source: Path | None = None) -> Path:
    candidate = Path(value).expanduser()
    candidate.parent.mkdir(parents=True, exist_ok=True)
    resolved = candidate.parent.resolve(strict=True) / candidate.name
    if source is not None and resolved == source:
        raise UnsafePathError("output path must not be the source media")
    return resolved


def _require_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise DependencyError(f"required local dependency not found: {name}")


def _doctor_capabilities(*, runner: CommandRunner | None = None) -> dict[str, dict[str, Any]]:
    capabilities: dict[str, dict[str, Any]] = {
        "ffmpeg": {"available": shutil.which("ffmpeg") is not None, "required": True},
        "ffprobe": {"available": shutil.which("ffprobe") is not None, "required": True},
    }
    for module in _OPTIONAL_MODULES:
        capabilities[module] = {"available": importlib.util.find_spec(module) is not None, "required": False}
    for executable in ("node", "blender"):
        capabilities[executable] = {"available": shutil.which(executable) is not None, "required": False}
    videotoolbox = False
    if capabilities["ffmpeg"]["available"]:
        try:
            completed = (runner or CommandRunner()).run(["ffmpeg", "-hide_banner", "-encoders"])
        except ExternalCommandError:
            pass
        else:
            videotoolbox = "h264_videotoolbox" in completed.stdout
    capabilities["h264_videotoolbox"] = {"available": videotoolbox, "required": False}
    return capabilities


def _analysis_transcriber(requested: bool) -> tuple[Any | None, str]:
    if not requested:
        return None, "none"
    transcriber = FasterWhisperTranscriber()
    if transcriber.availability().available:
        return transcriber, "faster-whisper-base"
    return _UnavailableTranscriber(), "faster-whisper-unavailable"


def _analyze(source: Path, *, cache_dir: Path | None, transcribe: bool) -> AnalysisArtifact:
    _require_binary("ffmpeg")
    _require_binary("ffprobe")
    transcriber, provider_fingerprint = _analysis_transcriber(transcribe)
    service = AnalysisService(cache_dir=cache_dir or source.parent / ".videoos-cache")
    return service.analyze(
        source,
        config=AnalysisConfig(provider_fingerprint=provider_fingerprint),
        transcriber=transcriber,
    )


def _analysis_summary(artifact: AnalysisArtifact) -> dict[str, Any]:
    return {
        "cache_key": artifact.source_hash,
        "duration": artifact.probe.duration,
        "resolution": (
            f"{artifact.probe.video.width}x{artifact.probe.video.height}"
            if artifact.probe.video and artifact.probe.video.width and artifact.probe.video.height
            else None
        ),
        "scenes": len(artifact.scene_boundaries),
        "silences": len(artifact.silence_regions),
        "transcription": next(
            (status.available for status in artifact.capabilities if status.name == "transcription"), False
        ),
        "warnings": artifact.warnings,
    }


def _project_directory(source: Path, output: Path | None) -> tuple[Path, Path]:
    if output is None:
        project_dir = source.parent / f"{source.stem}.videoos"
        render_output = project_dir / "renders" / f"{source.stem}.mp4"
    elif output.suffix:
        render_output = _output_path(output, source=source)
        project_dir = render_output.parent / f"{render_output.stem}.videoos"
    else:
        project_dir = Path(output).expanduser()
        render_output = project_dir / "renders" / f"{source.stem}.mp4"
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir.resolve(strict=True), render_output


def _analysis_reference(source_id: str, analysis_path: Path, artifact: AnalysisArtifact, project_dir: Path) -> AnalysisRef:
    return AnalysisRef(
        source_id=source_id,
        path=str(analysis_path.relative_to(project_dir)),
        source_sha256=artifact.source_hash,
        analysis_config_fingerprint=artifact.analysis_fingerprint,
        tool_fingerprint=artifact.tool_fingerprint,
    )


def _write_project(source: Path, artifact: AnalysisArtifact, *, project_dir: Path, target: TargetSpec, profile_name: str, captions: bool) -> tuple[ProjectManifest, Timeline, Path]:
    analysis_dir = project_dir / "analysis"
    analysis_dir.mkdir(exist_ok=True)
    analysis_path = analysis_dir / f"{artifact.source_hash}.json"
    save_model_atomic(analysis_path, artifact)
    manifest = ProjectManifest(
        version="1",
        project_id=artifact.source_hash,
        name=source.stem,
        sources=[SourceRef(id=artifact.source_hash, path=str(source))],
        target=target,
        analysis=[_analysis_reference(artifact.source_hash, analysis_path, artifact, project_dir)],
    )
    timeline = plan_talking_head(artifact, load_profile(profile_name), target)
    if not captions:
        timeline = timeline.model_copy(update={"captions": []})
    timeline.validate_against_sources({artifact.source_hash: artifact.probe.duration or 0.0})
    save_model_atomic(project_dir / "project.json", manifest)
    save_model_atomic(project_dir / "timeline.json", timeline)
    return manifest, timeline, analysis_path


def _load_project(project_path: Path) -> tuple[Path, ProjectManifest, Timeline]:
    resolved_project = _existing_file(project_path, label="project")
    project_dir = resolved_project.parent
    manifest = load_model(resolved_project, ProjectManifest)
    timeline = load_model(project_dir / "timeline.json", Timeline)
    source_ids = {source.id for source in manifest.sources}
    unknown_ids = {
        segment.source_id
        for track in timeline.tracks
        for segment in track.segments
        if segment.source_id not in source_ids
    }
    if unknown_ids:
        raise ValidationError("timeline references an unknown project source")
    for source in manifest.sources:
        _existing_file(Path(source.path), label=f"source {source.id}")
    return project_dir, manifest, timeline


def _persisted_analysis_duration(
    project_dir: Path,
    source: Path,
    reference: AnalysisRef,
) -> float | None:
    """Return a duration only when the project artifact still identifies this source."""
    declared_path = Path(reference.path)
    if declared_path.is_absolute():
        raise UnsafePathError("analysis artifact path must be relative to the project directory")
    try:
        artifact_path = (project_dir / declared_path).resolve(strict=True)
    except FileNotFoundError:
        return None
    try:
        artifact_path.relative_to(project_dir)
    except ValueError as error:
        raise UnsafePathError("analysis artifact path escapes the project directory") from error
    if not artifact_path.is_file() or not reference.is_cache_reusable:
        return None
    try:
        artifact = load_model(artifact_path, AnalysisArtifact)
    except ValueError:
        return None
    if (
        artifact.source_hash != reference.source_sha256
        or artifact.analysis_fingerprint != reference.analysis_config_fingerprint
        or artifact.tool_fingerprint != reference.tool_fingerprint
        or reference.source_sha256 != sha256_file(source)
    ):
        return None
    duration = artifact.probe.duration
    return duration if duration is not None else None


def _verified_source_durations(project_dir: Path, manifest: ProjectManifest) -> dict[str, float]:
    """Resolve authoritative source durations without invoking analysis orchestration."""
    durations: dict[str, float] = {}
    references_by_source: dict[str, list[AnalysisRef]] = {}
    for reference in manifest.analysis:
        references_by_source.setdefault(reference.source_id, []).append(reference)
    runner = CommandRunner()
    for source_ref in manifest.sources:
        source = _existing_file(Path(source_ref.path), label=f"source {source_ref.id}")
        duration = next(
            (
                persisted
                for reference in references_by_source.get(source_ref.id, [])
                if (persisted := _persisted_analysis_duration(project_dir, source, reference)) is not None
            ),
            None,
        )
        if duration is None:
            duration = probe_media(source, runner).duration
        if duration is None:
            raise ValidationError(f"source duration unavailable: {source_ref.id}")
        durations[source_ref.id] = duration
    return durations


def _render(project_path: Path, *, output: Path | None, dry_run: bool) -> dict[str, Any]:
    project_dir, manifest, timeline = _load_project(project_path)
    timeline.validate_against_sources(_verified_source_durations(project_dir, manifest))
    destination = output or project_dir / "renders" / f"{Path(manifest.name).stem}.mp4"
    destination = _output_path(destination)
    if not dry_run:
        _require_binary("ffmpeg")
    renderer = FfmpegRenderer()
    plan = renderer.build_plan(timeline, manifest, output=destination)
    result = renderer.render(plan, dry_run=dry_run)
    return {
        "project": str(project_path),
        "output": str(result.output) if result.output is not None else str(destination),
        "dry_run": result.dry_run,
        "warnings": list(plan.warnings),
    }


def _qa_report(
    output: Path,
    timeline: Timeline | None,
    *,
    target: TargetSpec | None = None,
) -> tuple[QAReport, Path]:
    resolved_output = _existing_file(output, label="output")
    _require_binary("ffprobe")
    probe = probe_media(resolved_output, CommandRunner())
    expected = QAExpectation(
        duration=timeline.duration_seconds() if timeline is not None else None,
        width=target.width if target is not None else None,
        height=target.height if target is not None else None,
        audio_required=False,
    )
    checks = check_output(resolved_output, expected, probe)
    if timeline is not None:
        source_durations = {
            segment.source_id: max(
                segment.source_end,
                0.0,
            )
            for track in timeline.tracks
            for segment in track.segments
        }
        checks.extend(check_timeline(timeline, source_durations))
    report = QAReport(
        passed=not any(check.status == "fail" for check in checks),
        duration=probe.duration,
        resolution=(
            f"{probe.video.width}x{probe.video.height}"
            if probe.video and probe.video.width and probe.video.height
            else None
        ),
        warnings=[check.message for check in checks if check.status == "warn"],
        checks=checks,
    )
    write_qa_report(resolved_output, report)
    return report, resolved_output.with_suffix(".qa.json")


@app.command()
def doctor(json_output: bool = typer.Option(False, "--json", help="Emit stable JSON.")) -> None:
    """Report local required and optional dependency capabilities."""

    capabilities = _doctor_capabilities()
    _emit("doctor", {"python": sys.version.split()[0], "machine": platform.machine(), "capabilities": capabilities}, json_output=json_output)
    if not all(capabilities[name]["available"] for name in ("ffmpeg", "ffprobe")):
        raise typer.Exit(code=2)


@app.command()
def analyze(
    input_path: Path = typer.Argument(..., metavar="INPUT"),  # noqa: B008
    output: Path | None = typer.Option(None, "--output", metavar="PATH"),  # noqa: B008
    cache_dir: Path | None = typer.Option(None, "--cache-dir", metavar="PATH"),  # noqa: B008
    transcribe: bool = typer.Option(False, "--transcribe"),
    profile: str = typer.Option("generic", "--profile"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Analyze one local source and persist an analysis artifact."""

    def operation() -> Mapping[str, Any]:
        load_profile(profile)  # Validate the requested policy without applying it to analysis.
        source = _existing_file(input_path, label="input")
        artifact = _analyze(source, cache_dir=cache_dir, transcribe=transcribe)
        artifact_path = _output_path(output or Path(f"{source}.analysis.json"), source=source)
        save_model_atomic(artifact_path, artifact)
        return {"artifact": str(artifact_path), **_analysis_summary(artifact)}

    _run("analyze", json_output=json_output, operation=operation)


@app.command()
def edit(
    input_path: Path = typer.Argument(..., metavar="INPUT"),  # noqa: B008
    profile: str = typer.Option("generic", "--profile"),
    aspect_ratio: str = typer.Option("16:9", "--aspect-ratio"),
    resolution: str = typer.Option("1920x1080", "--resolution"),
    output: Path | None = typer.Option(None, "--output", metavar="PATH"),  # noqa: B008
    transcribe: bool = typer.Option(False, "--transcribe"),
    no_captions: bool = typer.Option(False, "--no-captions"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Create a project, plan a deterministic timeline, and render locally."""

    def operation() -> Mapping[str, Any]:
        source = _existing_file(input_path, label="input")
        target = TargetSpec(aspect_ratio=aspect_ratio, resolution=resolution)
        artifact = _analyze(source, cache_dir=None, transcribe=transcribe)
        project_dir, render_output = _project_directory(source, output)
        manifest, timeline, analysis_path = _write_project(
            source,
            artifact,
            project_dir=project_dir,
            target=target,
            profile_name=profile,
            captions=not no_captions,
        )
        render_payload = _render(project_dir / "project.json", output=render_output, dry_run=dry_run)
        payload: dict[str, Any] = {
            "project": str(project_dir / "project.json"),
            "timeline": str(project_dir / "timeline.json"),
            "analysis": str(analysis_path),
            **render_payload,
        }
        if not dry_run:
            report, report_path = _qa_report(
                Path(render_payload["output"]),
                timeline,
                target=manifest.target,
            )
            payload["qa_report"] = str(report_path)
            payload["qa_passed"] = report.passed
        return payload

    _run("edit", json_output=False, operation=operation)


@app.command()
def shorts(
    input_path: Path = typer.Argument(..., metavar="INPUT"),  # noqa: B008
    count: int = typer.Option(3, "--count", min=1),
    output_dir: Path | None = typer.Option(None, "--output-dir", metavar="PATH"),  # noqa: B008
    transcribe: bool = typer.Option(False, "--transcribe"),
) -> None:
    """Persist bounded short-form candidates and local projects when FFmpeg is available."""

    def operation() -> Mapping[str, Any]:
        source = _existing_file(input_path, label="input")
        artifact = _analyze(source, cache_dir=None, transcribe=transcribe)
        destination = (output_dir or source.parent / f"{source.stem}.shorts").expanduser()
        destination.mkdir(parents=True, exist_ok=True)
        candidates = score_short_candidates(artifact, count=count)
        metadata = [
            _ShortMetadata(
                source_start=candidate.source_start,
                source_end=candidate.source_end,
                score=candidate.score,
                reason=candidate.reason,
                title=candidate.title,
                hook=_candidate_hook(candidate, artifact),
            )
            for candidate in candidates
        ]
        metadata_path = destination / "shorts.json"
        save_model_atomic(metadata_path, _ShortsArtifact(source=str(source), candidates=metadata))
        rendered_projects: list[str] = []
        if shutil.which("ffmpeg") is not None:
            for index, candidate in enumerate(candidates, start=1):
                project_dir = destination / f"short-{index:02d}.videoos"
                project_dir.mkdir(exist_ok=True)
                analysis_dir = project_dir / "analysis"
                analysis_dir.mkdir(exist_ok=True)
                analysis_path = analysis_dir / f"{artifact.source_hash}.json"
                save_model_atomic(analysis_path, artifact)
                target = TargetSpec(aspect_ratio="9:16", resolution="1080x1920")
                manifest = ProjectManifest(
                    version="1",
                    project_id=f"{artifact.source_hash}-{index}",
                    name=candidate.title,
                    sources=[SourceRef(id=artifact.source_hash, path=str(source))],
                    target=target,
                    analysis=[_analysis_reference(artifact.source_hash, analysis_path, artifact, project_dir)],
                )
                timeline = Timeline(
                    tracks=[
                        Track(
                            id="primary-video",
                            kind="video",
                            segments=[
                                SourceSegment(
                                    source_id=artifact.source_hash,
                                    source_start=candidate.source_start,
                                    source_end=candidate.source_end,
                                )
                            ],
                        )
                    ]
                )
                save_model_atomic(project_dir / "project.json", manifest)
                save_model_atomic(project_dir / "timeline.json", timeline)
                _render(project_dir / "project.json", output=None, dry_run=False)
                rendered_projects.append(str(project_dir / "project.json"))
        return {"metadata": str(metadata_path), "candidates": len(metadata), "rendered_projects": rendered_projects}

    _run("shorts", json_output=False, operation=operation)


def _candidate_hook(candidate: ShortCandidate, artifact: AnalysisArtifact) -> str | None:
    if artifact.transcript is None:
        return None
    excerpt = " ".join(
        region.text.strip()
        for region in artifact.transcript.regions
        if region.end >= candidate.source_start and region.start <= candidate.source_end
    ).strip()
    return excerpt[:160] or None


@app.command()
def render(
    project_json: Path = typer.Argument(..., metavar="PROJECT_JSON"),  # noqa: B008
    output: Path | None = typer.Option(None, "--output", metavar="PATH"),  # noqa: B008
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Render an existing structured project without invoking analysis."""

    _run("render", json_output=False, operation=lambda: _render(project_json, output=output, dry_run=dry_run))


@app.command()
def qa(
    output: Path = typer.Argument(..., metavar="OUTPUT"),  # noqa: B008
    timeline_path: Path | None = typer.Option(None, "--timeline", metavar="PATH"),  # noqa: B008
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Probe an output and write a QA evidence report without mutating inputs."""

    def operation() -> Mapping[str, Any]:
        timeline = load_model(_existing_file(timeline_path, label="timeline"), Timeline) if timeline_path else None
        report, report_path = _qa_report(output, timeline)
        payload = report.model_dump(mode="json")
        payload["report"] = str(report_path)
        return payload

    _run(
        "qa",
        json_output=json_output,
        operation=operation,
        failed=lambda payload: payload["passed"] is False,
    )
