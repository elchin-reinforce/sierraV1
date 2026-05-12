"""Generate or load retail seed data."""
from __future__ import annotations
from pathlib import Path

from taufreebench.core.serialization import load_json, save_json


DATA_DIR = Path(__file__).parent.parent.parent.parent.parent / "data" / "retail"


def get_data_dir() -> Path:
    return DATA_DIR


def load_retail_db(data_dir: Path | None = None) -> dict:
    d = data_dir or DATA_DIR
    return {
        "users": load_json(d / "users.json"),
        "products": load_json(d / "products.json"),
        "orders": load_json(d / "orders.json"),
    }


def load_retail_tasks(data_dir: Path | None = None) -> list[dict]:
    d = data_dir or DATA_DIR
    return load_json(d / "tasks.json")


def load_retail_policy(data_dir: Path | None = None) -> str:
    d = data_dir or DATA_DIR
    return (d / "policy.md").read_text(encoding="utf-8")


def seed_retail_data(data_dir: Path | None = None) -> None:
    """Verify seed data files exist; print status."""
    d = data_dir or DATA_DIR
    for fname in ["users.json", "products.json", "orders.json", "tasks.json", "policy.md"]:
        path = d / fname
        if path.exists():
            print(f"  [ok] {fname}")
        else:
            print(f"  [missing] {fname} — not found at {path}")
