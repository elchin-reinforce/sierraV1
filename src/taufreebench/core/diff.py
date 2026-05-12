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


def compact_diff_summary(diff: dict[str, Any]) -> dict[str, Any]:
    """Produce a compact human-readable summary of a DB diff."""
    if not diff:
        return {"clean": True}

    changed_tables: list[str] = []
    mismatched_values = 0
    missing_keys = 0
    extra_keys = 0
    changed_paths: list[str] = []

    def _walk(d: Any, prefix: str = "") -> None:
        nonlocal mismatched_values, missing_keys, extra_keys
        if not isinstance(d, dict):
            return
        typ = d.get("type")
        if typ == "value_mismatch" or typ == "type_mismatch":
            mismatched_values += 1
            if len(changed_paths) < 10:
                changed_paths.append(d.get("path", prefix))
        elif typ == "missing_key":
            missing_keys += 1
            if len(changed_paths) < 10:
                changed_paths.append(f"{prefix} [missing]")
        elif typ == "extra_key":
            extra_keys += 1
            if len(changed_paths) < 10:
                changed_paths.append(f"{prefix} [extra]")
        elif typ == "list_mismatch":
            mismatched_values += 1
            if len(changed_paths) < 10:
                changed_paths.append(d.get("path", prefix))
        else:
            for k, v in d.items():
                _walk(v, prefix=f"{prefix}.{k}" if prefix else k)

    for table, sub in diff.items():
        changed_tables.append(table)
        _walk(sub, prefix=table)

    return {
        "clean": False,
        "changed_tables": changed_tables,
        "mismatched_values": mismatched_values,
        "missing_keys": missing_keys,
        "extra_keys": extra_keys,
        "first_changed_paths": changed_paths[:10],
    }
