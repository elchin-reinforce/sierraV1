"""Run a single benchmark episode."""
from __future__ import annotations
from pathlib import Path
from typing import Any

from taufreebench.core.db import load_domain_db
from taufreebench.core.environment import BenchmarkEnvironment
from taufreebench.core.serialization import load_json
from taufreebench.core.types import EpisodeResult, Task
from taufreebench.core.tool import get_domain_tools


def _get_data_dir(domain: str, data_dir: Path | None = None) -> Path:
    if data_dir:
        return data_dir
    # run_episode.py → runners/ → taufreebench/ → src/ → project_root/
    return Path(__file__).parent.parent.parent.parent / "data"


def _load_policy(domain: str, data_dir: Path) -> str:
    policy_path = data_dir / domain / "policy.md"
    if policy_path.exists():
        return policy_path.read_text(encoding="utf-8")
    return f"You are a {domain} customer service agent. Be helpful and accurate."


def _load_tasks(domain: str, data_dir: Path) -> list[Task]:
    tasks_path = data_dir / domain / "tasks.json"
    raw = load_json(tasks_path)
    return [Task(**t) for t in raw]


def _make_agent(agent_type: str, agent_model: str | None = None):
    if agent_type == "rule":
        from taufreebench.agents.rule_based_agent import RuleBasedRetailAgent
        return RuleBasedRetailAgent()
    if agent_type == "ollama":
        from taufreebench.agents.ollama_tool_agent import OllamaToolAgent
        return OllamaToolAgent(model=agent_model)
    if agent_type == "gemini":
        from taufreebench.agents.gemini_tool_agent import GeminiToolAgent
        return GeminiToolAgent(model=agent_model)
    if agent_type == "groq":
        from taufreebench.agents.groq_tool_agent import GroqToolAgent
        return GroqToolAgent(model=agent_model)
    if agent_type == "openrouter":
        from taufreebench.agents.openrouter_tool_agent import OpenRouterToolAgent
        return OpenRouterToolAgent(model=agent_model)
    if agent_type == "auto-free":
        from taufreebench.providers.calibration import load_best_free_model
        best = load_best_free_model()
        if best:
            return _make_agent(best["provider"], best["model"])
        # Default to rule-based if no calibration
        from taufreebench.agents.rule_based_agent import RuleBasedRetailAgent
        return RuleBasedRetailAgent()
    raise ValueError(f"Unknown agent type: {agent_type}")


def _make_user(user_type: str, task_id: str, user_model: str | None = None):
    if user_type == "scripted":
        from taufreebench.users.scripted_user import ScriptedUser
        return ScriptedUser(task_id=task_id)
    if user_type in ("ollama", "auto-free"):
        from taufreebench.users.ollama_user import OllamaUser
        return OllamaUser(model=user_model or "llama3.1:8b")
    if user_type == "gemini":
        from taufreebench.users.gemini_user import GeminiUser
        return GeminiUser(model=user_model)
    if user_type == "groq":
        from taufreebench.users.groq_user import GroqUser
        return GroqUser(model=user_model)
    if user_type == "openrouter":
        from taufreebench.users.openrouter_user import OpenRouterUser
        return OpenRouterUser(model=user_model)
    raise ValueError(f"Unknown user type: {user_type}")


def run_episode_for_task(
    domain: str,
    task_id: str,
    agent_type: str = "rule",
    agent_model: str | None = None,
    user_type: str = "scripted",
    user_model: str | None = None,
    data_dir: Path | None = None,
) -> EpisodeResult:
    """Run one episode for a named task."""
    # Ensure domain tools are registered
    _ensure_domain_tools(domain)

    base_data_dir = _get_data_dir(domain, data_dir)
    db = load_domain_db(domain, base_data_dir)
    policy = _load_policy(domain, base_data_dir)
    tasks = _load_tasks(domain, base_data_dir)
    tools = get_domain_tools(domain)

    task_map = {t.id: t for t in tasks}
    if task_id not in task_map:
        raise ValueError(f"Task '{task_id}' not found. Available: {list(task_map.keys())}")
    task = task_map[task_id]

    agent = _make_agent(agent_type, agent_model)
    user = _make_user(user_type, task_id, user_model)

    env = BenchmarkEnvironment(
        domain_name=domain,
        db=db,
        tools=tools,
        policy=policy,
        task=task,
        user=user,
        agent=agent,
    )
    return env.run_episode()


def _ensure_domain_tools(domain: str) -> None:
    if domain == "retail":
        import taufreebench.domains.retail.tools  # noqa: F401
    elif domain == "airline":
        try:
            import taufreebench.domains.airline.tools  # noqa: F401
        except ImportError:
            pass
