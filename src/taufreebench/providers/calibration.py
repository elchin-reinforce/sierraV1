"""Auto-calibrate: rank available free models and save best choice."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from .model_registry import ModelCandidate, get_provider
from .free_model_discovery import get_available_candidates

CALIBRATION_TASK_IDS = ["retail_task_001", "retail_task_004", "retail_task_005"]
RUNS_DIR = Path(__file__).parent.parent.parent.parent / "runs" / "calibration"


def run_calibration(
    domain: str = "retail",
    max_models: int = 6,
    data_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Run calibration tasks for each available free model and rank them."""
    from taufreebench.runners.run_episode import run_episode_for_task

    candidates = get_available_candidates()[:max_models]
    if not candidates:
        print("No available free models found. Run: python -m taufreebench.cli discover-free-models")
        return []

    results: list[dict[str, Any]] = []
    for candidate in candidates:
        print(f"\nCalibrating {candidate.provider}/{candidate.model} ...")
        try:
            provider = get_provider(candidate)
        except Exception as e:
            print(f"  Skipping — could not create provider: {e}")
            continue

        task_results = []
        for task_id in CALIBRATION_TASK_IDS:
            try:
                episode = run_episode_for_task(
                    domain=domain,
                    task_id=task_id,
                    agent_type="ollama" if candidate.provider == "ollama" else candidate.provider,
                    agent_model=candidate.model,
                    user_type="scripted",
                    data_dir=data_dir,
                )
                task_results.append(episode.model_dump())
                print(f"  {task_id}: reward={episode.reward}")
            except Exception as e:
                print(f"  {task_id}: error — {e}")
                task_results.append({"reward": 0, "turns": 0, "tool_calls": 0, "invalid_tool_calls": 0, "latency_seconds": None, "failure_reason": str(e)})

        n = len(task_results)
        successes = sum(1 for t in task_results if t.get("reward", 0) == 1)
        total_tools = sum(t.get("tool_calls", 0) for t in task_results)
        invalid = sum(t.get("invalid_tool_calls", 0) for t in task_results)
        latencies = [t["latency_seconds"] for t in task_results if t.get("latency_seconds")]
        mean_latency = sum(latencies) / len(latencies) if latencies else None

        row = {
            "provider": candidate.provider,
            "model": candidate.model,
            "local": candidate.local,
            "pass_1": successes / n if n > 0 else 0.0,
            "invalid_tool_call_rate": (invalid / total_tools) if total_tools > 0 else 0.0,
            "mean_latency_seconds": mean_latency,
            "successes": successes,
            "trials": n,
        }
        results.append(row)

    # Sort by: pass_1 desc, invalid rate asc, latency asc, local preferred
    results.sort(key=lambda r: (
        -r["pass_1"],
        r["invalid_tool_call_rate"],
        r["mean_latency_seconds"] or float("inf"),
        0 if r["local"] else 1,
    ))

    # Save results
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    results_path = RUNS_DIR / "free_model_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {results_path}")

    if results:
        best = results[0]
        best_path = RUNS_DIR / "best_free_model.json"
        with open(best_path, "w") as f:
            json.dump({"provider": best["provider"], "model": best["model"]}, f, indent=2)
        print(f"Best model: {best['provider']}/{best['model']} (saved to {best_path})")

    return results


def load_best_free_model() -> dict[str, str] | None:
    path = RUNS_DIR / "best_free_model.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)
