"""Safe, deterministic FFmpeg filter graph and argv compilation."""

from __future__ import annotations

import shutil
import stat
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from videoos.analysis.models import CapabilityStatus
from videoos.analysis.runner import CommandRunner
from videoos.core.errors import ExternalCommandError, UnsafePathError
from videoos.core.models import ProjectManifest, TargetSpec, Timeline
from videoos.core.paths import ensure_output_path, publish_staged_output

from .operations import RenderOperation, RenderPlan, RenderResult

_ALLOWED_VIDEO_CODECS = frozenset({"libx264", "h264_videotoolbox"})
_ALLOWED_CAPTION_SUFFIXES = frozenset({".ass", ".srt"})
_MAX_ZOOM_SCALE = 1.25
_MAX_DIAGNOSTIC_CHARS = 512
_LOUDNORM_FILTER = "loudnorm=I=-16:TP=-1.5:LRA=11"


def _number(value: float) -> str:
    """Format already-validated finite values without locale or exponent variance."""
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def escape_subtitles_filter_path(path: Path) -> str:
    """Escape a generated subtitle file path for FFmpeg's quoted filter value."""
    value = path.as_posix()
    if "\x00" in value:
        raise UnsafePathError("subtitle path contains NUL")
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")


def _video_chain(operation: RenderOperation, target: TargetSpec) -> str:
    transform = operation.transform
    x = "(in_w-out_w)/2"
    y = "(in_h-out_h)/2"
    if transform is not None and transform.crop_x is not None:
        x = f"min(max(0,{_number(transform.crop_x)}),in_w-out_w)"
    if transform is not None and transform.crop_y is not None:
        y = f"min(max(0,{_number(transform.crop_y)}),in_h-out_h)"
    filters = [
        f"trim=start={_number(operation.source_start)}:end={_number(operation.source_end)}",
        "setpts=PTS-STARTPTS",
        f"scale={target.width}:{target.height}:force_original_aspect_ratio=increase",
        f"crop={target.width}:{target.height}:x='{x}':y='{y}'",
    ]
    if transform is not None and transform.zoom_scale is not None:
        zoom = min(transform.zoom_scale, _MAX_ZOOM_SCALE)
        filters.append(
            f"zoompan=z='min({_number(zoom)},zoom+0.0)':d=1:s={target.width}x{target.height}:fps=30"
        )
    return ",".join(filters)


def build_filter_graph(
    operations: Sequence[RenderOperation],
    target: TargetSpec,
    *,
    caption_file: Path | None = None,
    include_audio: bool,
) -> str:
    """Compile the allowlisted video/audio filters for an already-safe operation trace."""
    if not operations:
        raise ValueError("a render requires at least one video segment")
    if not include_audio and len(operations) == 1 and caption_file is None:
        operation = operations[0]
        return f"[{operation.input_index}:v]{_video_chain(operation, target)}[vout]"

    chains: list[str] = []
    inputs: list[str] = []
    for index, operation in enumerate(operations):
        video_label = f"v{index}"
        chains.append(f"[{operation.input_index}:v]{_video_chain(operation, target)}[{video_label}]")
        inputs.append(f"[{video_label}]")
        if include_audio:
            audio_label = f"a{index}"
            chains.append(
                f"[{operation.input_index}:a]atrim=start={_number(operation.source_start)}:"
                f"end={_number(operation.source_end)},asetpts=PTS-STARTPTS[{audio_label}]"
            )
            inputs.append(f"[{audio_label}]")

    if include_audio:
        chains.append(f"{''.join(inputs)}concat=n={len(operations)}:v=1:a=1[vconcat][anormalized]")
        chains.append(f"[anormalized]{_LOUDNORM_FILTER}[aout]")
    else:
        chains.append(f"{''.join(inputs)}concat=n={len(operations)}:v=1:a=0[vconcat]")

    if caption_file is None:
        chains.append("[vconcat]null[vout]")
    else:
        escaped_caption = escape_subtitles_filter_path(caption_file)
        chains.append(f"[vconcat]subtitles=filename='{escaped_caption}'[vout]")
    return ";".join(chains)


def _capability_reports_videotoolbox(
    capabilities: Mapping[str, bool] | Iterable[CapabilityStatus] | None,
) -> bool:
    if capabilities is None:
        return False
    if isinstance(capabilities, Mapping):
        return capabilities.get("h264_videotoolbox") is True
    return any(item.name == "h264_videotoolbox" and item.available for item in capabilities)


def _controlled_caption_file(path: Path) -> Path:
    resolved = path.resolve(strict=True)
    if resolved.suffix.lower() not in _ALLOWED_CAPTION_SUFFIXES:
        raise UnsafePathError("caption file must be a generated .srt or .ass file")
    if not stat.S_ISREG(resolved.stat().st_mode):
        raise UnsafePathError("caption file must be a regular file")
    return resolved


def _source_operations(timeline: Timeline, manifest: ProjectManifest) -> tuple[RenderOperation, ...]:
    source_paths = {source.id: Path(source.path).resolve(strict=True) for source in manifest.sources}
    video_segments = sorted(
        (segment for track in timeline.tracks if track.kind == "video" for segment in track.segments),
        key=lambda segment: (segment.timeline_start, segment.source_id, segment.source_start),
    )
    input_indices: dict[Path, int] = {}
    operations: list[RenderOperation] = []
    for segment in video_segments:
        source = source_paths.get(segment.source_id)
        if source is None:
            raise ValueError(f"timeline references unknown source: {segment.source_id}")
        input_index = input_indices.setdefault(source, len(input_indices))
        operations.append(
            RenderOperation(
                source_id=segment.source_id,
                source_path=source,
                input_index=input_index,
                source_start=segment.source_start,
                source_end=segment.source_end,
                transform=segment.transform,
                has_audio=segment.audio is not None,
            )
        )
    if not operations:
        raise ValueError("timeline has no video source segments")
    return tuple(operations)


def _input_paths(operations: Sequence[RenderOperation]) -> tuple[Path, ...]:
    paths_by_index = {operation.input_index: operation.source_path for operation in operations}
    return tuple(path for _, path in sorted(paths_by_index.items()))


def _compile_argv(
    input_paths: Sequence[Path],
    filter_graph: str,
    *,
    has_audio: bool,
    video_codec: str,
    temp_output: Path,
) -> tuple[str, ...]:
    if video_codec not in _ALLOWED_VIDEO_CODECS:
        raise ValueError("unsupported video codec")
    argv = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for source_path in input_paths:
        argv.extend(("-i", str(source_path)))
    argv.extend(("-filter_complex", filter_graph, "-map", "[vout]"))
    if has_audio:
        argv.extend(("-map", "[aout]"))
    argv.extend(("-c:v", video_codec, "-pix_fmt", "yuv420p"))
    if has_audio:
        argv.extend(("-c:a", "aac"))
    argv.extend(("-movflags", "+faststart", "-f", "mp4", str(temp_output)))
    return tuple(argv)


class FfmpegRenderer:
    """Build local FFmpeg plans and publish only verified, exclusive staged outputs."""

    def __init__(
        self,
        *,
        runner: CommandRunner | None = None,
        hardware_encoding: bool = False,
        capabilities: Mapping[str, bool] | Iterable[CapabilityStatus] | None = None,
    ) -> None:
        self._runner = CommandRunner() if runner is None else runner
        self._hardware_encoding = hardware_encoding
        self._capabilities = capabilities

    def build_plan(
        self,
        timeline: Timeline,
        manifest: ProjectManifest,
        *,
        output: Path,
        caption_file: Path | None = None,
    ) -> RenderPlan:
        destination = Path(output)
        operations = _source_operations(timeline, manifest)
        source_paths = {operation.source_path.resolve(strict=True) for operation in operations}
        if destination.resolve(strict=False) in source_paths:
            raise UnsafePathError("render output must not be a source path")
        destination = ensure_output_path(destination, project_dir=destination.parent)
        controlled_caption = _controlled_caption_file(caption_file) if caption_file is not None else None
        has_audio = all(operation.has_audio for operation in operations)
        warnings: list[str] = []
        if any(operation.has_audio for operation in operations) and not has_audio:
            warnings.append("audio omitted because one or more video segments have no audio stream")
        if timeline.captions and controlled_caption is None:
            warnings.append("caption cues were not burned because no controlled caption file was supplied")
        if any(
            operation.transform is not None
            and operation.transform.zoom_scale is not None
            and operation.transform.zoom_scale > _MAX_ZOOM_SCALE
            for operation in operations
        ):
            warnings.append(f"zoom scales are capped at {_MAX_ZOOM_SCALE}")
        video_codec = "h264_videotoolbox" if (
            self._hardware_encoding and _capability_reports_videotoolbox(self._capabilities)
        ) else "libx264"
        input_paths = _input_paths(operations)
        filter_graph = build_filter_graph(
            operations, manifest.target, caption_file=controlled_caption, include_audio=has_audio
        )
        planned_stage = destination.with_name(f".{destination.name}.videoos-plan.part")
        argv = _compile_argv(
            input_paths,
            filter_graph,
            has_audio=has_audio,
            video_codec=video_codec,
            temp_output=planned_stage,
        )
        return RenderPlan(
            argv=argv,
            filter_graph=filter_graph,
            operations=operations,
            expected_duration_seconds=sum(operation.duration_seconds for operation in operations),
            warnings=tuple(warnings),
            output=destination,
            temp_output=planned_stage,
            input_paths=input_paths,
            target=manifest.target,
            caption_file=controlled_caption,
            has_audio=has_audio,
            video_codec=video_codec,
        )

    def render(self, plan: RenderPlan, *, dry_run: bool = False) -> RenderResult:
        if dry_run:
            return RenderResult(plan=plan, output=None, dry_run=True, diagnostics="")

        staged_path: Path | None = None
        try:
            with tempfile.TemporaryDirectory(dir=plan.output.parent, prefix=".videoos-render-") as resources:
                runtime_caption: Path | None = None
                if plan.caption_file is not None:
                    runtime_caption = Path(resources) / f"captions{plan.caption_file.suffix.lower()}"
                    shutil.copyfile(plan.caption_file, runtime_caption)
                with tempfile.NamedTemporaryFile(
                    dir=plan.output.parent,
                    prefix=f".{plan.output.name}.",
                    suffix=".part",
                    delete=False,
                ) as staged:
                    staged_path = Path(staged.name)
                runtime_graph = build_filter_graph(
                    plan.operations,
                    plan.target,
                    caption_file=runtime_caption,
                    include_audio=plan.has_audio,
                )
                runtime_argv = _compile_argv(
                    plan.input_paths,
                    runtime_graph,
                    has_audio=plan.has_audio,
                    video_codec=plan.video_codec,
                    temp_output=staged_path,
                )
                completed = self._runner.run(runtime_argv)
                if not staged_path.is_file() or staged_path.stat().st_size == 0:
                    raise ExternalCommandError("ffmpeg completed without a non-empty staged output")
                try:
                    output = publish_staged_output(
                        staged_path, plan.output, project_dir=plan.output.parent
                    )
                except FileExistsError as exc:
                    raise UnsafePathError("render output became occupied before publication") from exc
                staged_path = None
                diagnostics = (getattr(completed, "stdout", "") + getattr(completed, "stderr", ""))[
                    :_MAX_DIAGNOSTIC_CHARS
                ]
                return RenderResult(plan=plan, output=output, dry_run=False, diagnostics=diagnostics)
        finally:
            if staged_path is not None:
                staged_path.unlink(missing_ok=True)
