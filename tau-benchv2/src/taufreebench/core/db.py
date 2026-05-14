"""JSON database loading and management."""
from __future__ import annotations
import copy
from pathlib import Path
from typing import Any

from .serialization import load_json, save_json


DOMAIN_DB_SHAPES: dict[str, list[str]] = {
    "retail": ["users", "products", "orders"],
    "airline": ["users", "flights", "reservations"],
}


def load_domain_db(domain: str, data_dir: Path) -> dict[str, Any]:
    """Load all JSON files for a domain into a single dict."""
    shape = DOMAIN_DB_SHAPES.get(domain)
    if shape is None:
        raise ValueError(f"Unknown domain: {domain}")
    db: dict[str, Any] = {}
    for key in shape:
        file_path = data_dir / domain / f"{key}.json"
        if file_path.exists():
            db[key] = load_json(file_path)
        else:
            db[key] = {}
    return db


def save_domain_db(domain: str, db: dict[str, Any], data_dir: Path) -> None:
    """Save domain DB back to individual JSON files."""
    shape = DOMAIN_DB_SHAPES.get(domain, list(db.keys()))
    for key in shape:
        if key in db:
            save_json(db[key], data_dir / domain / f"{key}.json")


def deep_copy_db(db: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(db)
