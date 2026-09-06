from pathlib import Path

from .errors import UnsafePathError


def _resolved_base(base_dir: Path | None) -> Path:
    base = (base_dir if base_dir is not None else Path.cwd()).resolve(strict=True)
    if not base.is_dir():
        raise UnsafePathError(f"base directory is not a directory: {base}")
    return base


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def resolve_input_path(path: str | Path, *, base_dir: Path | None = None) -> Path:
    """Resolve an existing input path while keeping it inside ``base_dir``."""
    base = _resolved_base(base_dir)
    candidate = Path(path)
    unresolved = candidate if candidate.is_absolute() else base / candidate
    resolved = unresolved.resolve(strict=False)
    if not _is_within(resolved, base):
        raise UnsafePathError(f"input path escapes base directory: {path}")
    return resolved.resolve(strict=True)


def ensure_output_path(path: str | Path, *, project_dir: Path | None = None) -> Path:
    """Validate a new output path inside ``project_dir`` without touching files."""
    project = _resolved_base(project_dir)
    candidate = Path(path)
    unresolved = candidate if candidate.is_absolute() else project / candidate
    parent = unresolved.parent.resolve(strict=True)
    resolved = parent / unresolved.name
    if not _is_within(resolved, project):
        raise UnsafePathError(f"output path escapes project directory: {path}")
    if resolved.exists():
        raise UnsafePathError(f"output path already exists: {resolved}")
    return resolved
