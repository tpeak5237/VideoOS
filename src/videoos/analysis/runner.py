"""Safe local subprocess execution for media analysis tools."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence

from videoos.core.errors import ExternalCommandError

_MAX_DIAGNOSTIC_CHARS = 512


def _excerpt(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return value[:_MAX_DIAGNOSTIC_CHARS]


class CommandRunner:
    """Run local tools without invoking a shell."""

    def run(
        self, args: Sequence[str], *, timeout: float | None = None
    ) -> subprocess.CompletedProcess[str]:
        if isinstance(args, str) or not args:
            raise ValueError("command arguments must contain an executable")
        command = list(args)
        executable = command[0][:128]
        try:
            result = subprocess.run(
                command,
                shell=False,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise ExternalCommandError(f"external command {executable!r} not found") from exc
        except subprocess.TimeoutExpired as exc:
            diagnostic = _excerpt(exc.stderr)
            message = f"external command {executable!r} timed out"
            if diagnostic:
                message = f"{message}: {diagnostic}"
            raise ExternalCommandError(message) from exc

        if result.returncode != 0:
            diagnostic = _excerpt(result.stderr)
            message = f"external command {executable!r} failed with exit code {result.returncode}"
            if diagnostic:
                message = f"{message}: {diagnostic}"
            raise ExternalCommandError(message)
        return result
