"""JSON serialization helpers."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any


def load_json(path: Path | str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: Any, path: Path | str, indent: int = 2) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def pretty_json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)
