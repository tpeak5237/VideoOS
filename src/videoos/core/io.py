"""Atomic UTF-8 persistence for structured VideoOS models."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel


def load_model[T: BaseModel](path: Path, model_type: type[T]) -> T:
    """Load a validated model without reflecting untrusted file contents in errors."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read structured model at {path}: {exc}") from exc
    return model_type.model_validate(payload)


def save_model_atomic(path: Path, model: BaseModel) -> None:
    """Durably replace ``path`` with UTF-8 JSON using a sibling temporary file."""
    destination = Path(path)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent, prefix=f".{destination.name}.", suffix=".tmp", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(model.model_dump(mode="json"), temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, destination)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
