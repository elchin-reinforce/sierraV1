"""Tool registry and decorator."""
from __future__ import annotations
import functools
import inspect
from typing import Any, Callable


class ToolDefinition:
    def __init__(
        self,
        fn: Callable,
        name: str,
        description: str,
        parameters: dict[str, Any],
        read_only: bool,
    ):
        self.fn = fn
        self.name = name
        self.description = description
        self.parameters = parameters
        self.read_only = read_only

    def __call__(self, db: dict[str, Any], **kwargs) -> Any:
        return self.fn(db, **kwargs)

    def to_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def __repr__(self) -> str:
        return f"ToolDefinition(name={self.name!r}, read_only={self.read_only})"


_TOOL_REGISTRY: dict[str, dict[str, ToolDefinition]] = {}


def tool(
    name: str | None = None,
    description: str = "",
    parameters: dict[str, Any] | None = None,
    read_only: bool = True,
    domain: str = "retail",
):
    """Decorator to register a function as a tool."""
    def decorator(fn: Callable) -> ToolDefinition:
        tool_name = name or fn.__name__
        tool_params = parameters or _infer_parameters(fn)
        td = ToolDefinition(
            fn=fn,
            name=tool_name,
            description=description,
            parameters=tool_params,
            read_only=read_only,
        )
        if domain not in _TOOL_REGISTRY:
            _TOOL_REGISTRY[domain] = {}
        _TOOL_REGISTRY[domain][tool_name] = td
        return td
    return decorator


def get_domain_tools(domain: str) -> dict[str, ToolDefinition]:
    return _TOOL_REGISTRY.get(domain, {})


def _infer_parameters(fn: Callable) -> dict[str, Any]:
    """Infer JSON schema parameters from function signature."""
    sig = inspect.signature(fn)
    props: dict[str, Any] = {}
    required: list[str] = []
    for param_name, param in sig.parameters.items():
        if param_name == "db":
            continue
        annotation = param.annotation
        props[param_name] = _annotation_to_schema(annotation)
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
    return {
        "type": "object",
        "properties": props,
        "required": required,
    }


def _annotation_to_schema(annotation: Any) -> dict[str, Any]:
    if annotation is inspect.Parameter.empty:
        return {"type": "string"}
    origin = getattr(annotation, "__origin__", None)
    if annotation is str:
        return {"type": "string"}
    if annotation is int:
        return {"type": "integer"}
    if annotation is float:
        return {"type": "number"}
    if annotation is bool:
        return {"type": "boolean"}
    if origin is list:
        args = getattr(annotation, "__args__", (str,))
        return {"type": "array", "items": _annotation_to_schema(args[0])}
    if origin is dict:
        return {"type": "object"}
    return {"type": "string"}
