"""Stable local persistence for QA reports."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from videoos.core.paths import publish_staged_output

from .models import QAReport


def _destination(path: Path) -> Path:
    return path if path.name.endswith(".qa.json") else path.with_suffix(".qa.json")


def write_qa_report(path: Path, report: QAReport, *, exclusive: bool = False) -> None:
    """Atomically write a sorted JSON report beside an output media file."""
    destination = _destination(Path(path))
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        report.model_dump(mode="json"), allow_nan=False, ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent, prefix=f".{destination.name}.", suffix=".tmp", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(encoded)
            temporary.flush()
            os.fsync(temporary.fileno())
        if exclusive:
            publish_staged_output(temporary_path, destination, project_dir=destination.parent)
        else:
            os.replace(temporary_path, destination)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
