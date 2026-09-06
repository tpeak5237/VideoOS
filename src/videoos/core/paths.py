import os
import stat
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


def ensure_output_path(
    path: str | Path,
    *,
    project_dir: Path | None = None,
    allow_existing: bool = False,
) -> Path:
    """Validate an output path inside ``project_dir`` without touching files."""
    project = _resolved_base(project_dir)
    candidate = Path(path)
    unresolved = candidate if candidate.is_absolute() else project / candidate
    parent = unresolved.parent.resolve(strict=True)
    resolved = parent / unresolved.name
    if not _is_within(resolved, project):
        raise UnsafePathError(f"output path escapes project directory: {path}")
    if resolved.exists() and not allow_existing:
        raise UnsafePathError(f"output path already exists: {resolved}")
    return resolved


def publish_staged_output(
    staged_path: str | Path,
    destination_path: str | Path,
    *,
    project_dir: Path | None = None,
) -> Path:
    """Publish a same-directory stage exactly once without following links.

    The destination is created with an exclusive hard-link operation. A target
    that appears after validation, including a symlink or hard link, therefore
    causes the atomic operation to fail without replacing it.
    """
    project = _resolved_base(project_dir)
    staged = Path(staged_path)
    destination = Path(destination_path)
    staged_parent = staged.parent.resolve(strict=True)
    destination_parent = destination.parent.resolve(strict=True)
    if staged_parent != destination_parent or not _is_within(staged_parent, project):
        raise UnsafePathError("staged and destination paths must share a project directory")
    if not _is_within(destination_parent / destination.name, project):
        raise UnsafePathError(f"output path escapes project directory: {destination_path}")
    if not _is_within(staged_parent / staged.name, project):
        raise UnsafePathError(f"staged path escapes project directory: {staged_path}")

    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory_fd = os.open(staged_parent, directory_flags)
    try:
        staged_stat = os.stat(staged.name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(staged_stat.st_mode):
            raise UnsafePathError(f"staged path is not a regular file: {staged_path}")
        os.link(
            staged.name,
            destination.name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )
        os.unlink(staged.name, dir_fd=directory_fd)
    finally:
        os.close(directory_fd)
    return destination_parent / destination.name
