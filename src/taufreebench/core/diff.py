"""Database diff utilities."""
from __future__ import annotations
from typing import Any


def compute_db_diff(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    """Produce a human-readable diff between two DB states."""
    diff: dict[str, Any] = {}
    all_keys = set(expected) | set(actual)
    for key in sorted(all_keys):
        if key not in expected:
            diff[key] = {"type": "extra_key", "actual": actual[key]}
        elif key not in actual:
            diff[key] = {"type": "missing_key", "expected": expected[key]}
        else:
            sub = _diff_value(expected[key], actual[key], path=key)
            if sub:
                diff[key] = sub
    return diff


def _diff_value(expected: Any, actual: Any, path: str = "") -> Any:
    if type(expected) != type(actual):
        return {"type": "type_mismatch", "expected": expected, "actual": actual, "path": path}
    if isinstance(expected, dict):
        return _diff_dict(expected, actual, path)
    if isinstance(expected, list):
        return _diff_list(expected, actual, path)
    if expected != actual:
        return {"type": "value_mismatch", "expected": expected, "actual": actual, "path": path}
    return None


def _diff_dict(expected: dict, actual: dict, path: str) -> dict | None:
    sub_diffs: dict[str, Any] = {}
    all_keys = set(expected) | set(actual)
    for k in sorted(all_keys):
        if k not in expected:
            sub_diffs[k] = {"type": "extra_key", "actual": actual[k]}
        elif k not in actual:
            sub_diffs[k] = {"type": "missing_key", "expected": expected[k]}
        else:
            d = _diff_value(expected[k], actual[k], path=f"{path}.{k}")
            if d is not None:
                sub_diffs[k] = d
    return sub_diffs if sub_diffs else None


def _diff_list(expected: list, actual: list, path: str) -> dict | None:
    if expected != actual:
        return {
            "type": "list_mismatch",
            "expected": expected,
            "actual": actual,
            "path": path,
        }
    return None


def diffs_are_empty(diff: dict[str, Any]) -> bool:
    return not bool(diff)
