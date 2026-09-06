"""Safe local subprocess execution for media analysis tools."""

from __future__ import annotations

import math
import os
import selectors
import signal
import subprocess
import time
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

    def __init__(self, *, default_timeout: float | None = None, max_output_bytes: int | None = None):
        self.default_timeout = float(os.environ.get("VIDEOOS_COMMAND_TIMEOUT_SECONDS", "3600")) if default_timeout is None else default_timeout
        self.max_output_bytes = int(os.environ.get("VIDEOOS_COMMAND_MAX_OUTPUT_BYTES", "16777216")) if max_output_bytes is None else max_output_bytes
        if not math.isfinite(self.default_timeout) or self.default_timeout <= 0 or self.max_output_bytes <= 0:
            raise ValueError("command execution/output limits must be positive and finite")

    def run(
        self, args: Sequence[str], *, timeout: float | None = None
    ) -> subprocess.CompletedProcess[str]:
        if isinstance(args, str) or not args:
            raise ValueError("command arguments must contain an executable")
        command = list(args)
        if sum(len(arg) for arg in command) > 131072:
            raise ValueError("command arguments exceed the execution limit")
        executable = command[0][:128]
        limit = self.default_timeout if timeout is None else timeout
        if not math.isfinite(limit) or limit <= 0:
            raise ValueError("command timeout must be positive and finite")
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        try:
            with subprocess.Popen(command, shell=False, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  start_new_session=True) as process:
                try:
                    deadline = time.monotonic() + limit
                    with selectors.DefaultSelector() as selector:
                        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
                        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
                        while selector.get_map():
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                raise ExternalCommandError(f"external command {executable!r} timed out")
                            for key, _ in selector.select(min(remaining, 0.1)):
                                data = os.read(key.fileobj.fileno(), 65536)
                                if not data:
                                    selector.unregister(key.fileobj)
                                    continue
                                buffer = buffers[key.data]
                                if len(buffer) + len(data) > self.max_output_bytes:
                                    raise ExternalCommandError(f"external command {executable!r} exceeded output limit")
                                buffer.extend(data)
                    process.wait(timeout=max(0.001, deadline - time.monotonic()))
                except BaseException:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
                    raise
                result = subprocess.CompletedProcess(command, process.returncode,
                    buffers["stdout"].decode("utf-8", errors="replace"),
                    buffers["stderr"].decode("utf-8", errors="replace"))
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
