"""Tool registry for the agent.

Phase 3: simple in-process stub tools (deterministic, no network).
Phase 4: MCP tools are registered at startup and live alongside the stubs.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional

from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class ToolSpec:
    name: str
    description: str
    arguments_schema: Dict[str, str]   # arg_name -> human description
    handler: Callable[[Dict[str, Any]], Any]
    source: str = "local"              # "local" | "mcp:<server>"
    async_handler: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, Any]]] = None  # async version


def _get_current_time(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"utc": datetime.now(timezone.utc).isoformat()}


def _echo(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"echo": str(args.get("text", ""))}


def _word_count(args: Dict[str, Any]) -> Dict[str, Any]:
    text = str(args.get("text", ""))
    return {"words": len(text.split()), "characters": len(text)}


_TOOLS: Dict[str, ToolSpec] = {
    t.name: t
    for t in [
        ToolSpec(
            name="get_current_time",
            description="Returns the current UTC time in ISO 8601 format. Use when the user asks for the time or date.",
            arguments_schema={},
            handler=_get_current_time,
        ),
        ToolSpec(
            name="echo",
            description="Echoes the provided text back. Use when the user explicitly asks to echo or repeat text.",
            arguments_schema={"text": "The text to echo back."},
            handler=_echo,
        ),
        ToolSpec(
            name="word_count",
            description="Counts words and characters of a provided text. Use when the user asks to count words/characters.",
            arguments_schema={"text": "The text to count."},
            handler=_word_count,
        ),
    ]
}


def list_tools() -> List[ToolSpec]:
    return list(_TOOLS.values())


def get_tool(name: str) -> ToolSpec | None:
    return _TOOLS.get(name)


def tools_catalog_for_prompt() -> str:
    lines = []
    for t in list_tools():
        args = ", ".join(f"{k} ({v})" for k, v in t.arguments_schema.items()) or "(none)"
        lines.append(f"- {t.name} [{t.source}]: {t.description} Args: {args}")
    return "\n".join(lines)


def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    spec = get_tool(name)
    if spec is None:
        raise ValueError(f"Unknown tool: {name}")
    return spec.handler(arguments or {})


async def execute_tool_async(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool asynchronously (supports MCP tools)."""
    spec = get_tool(name)
    if spec is None:
        raise ValueError(f"Unknown tool: {name}")
    
    # Use async handler if available (MCP tools), otherwise run sync handler
    if spec.async_handler:
        return await spec.async_handler(arguments or {})
    else:
        # Run sync handler in executor to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: spec.handler(arguments or {}))


# --------------------------- MCP registration -------------------------------

def _extract_args_schema(lc_tool: Any) -> Dict[str, str]:
    """Best-effort: derive {name: description} from a LangChain tool's args_schema."""
    try:
        schema_cls = getattr(lc_tool, "args_schema", None)
        if schema_cls is None:
            return {}
        # Pydantic v2
        if hasattr(schema_cls, "model_fields"):
            return {
                name: (f.description or f.annotation.__name__ if f.annotation else "")
                for name, f in schema_cls.model_fields.items()
            }
        # Pydantic v1 fallback
        if hasattr(schema_cls, "__fields__"):
            return {n: (f.field_info.description or "") for n, f in schema_cls.__fields__.items()}
    except Exception:
        pass
    return {}


def _wrap_mcp_tool(lc_tool: Any, server_name: Optional[str] = None) -> ToolSpec:
    """Wrap a LangChain BaseTool (from MCP adapter) as a ToolSpec."""
    def _handler(args: Dict[str, Any]) -> Any:
        # Fallback sync handler (may not work for all MCP tools)
        try:
            return lc_tool.invoke(args or {})
        except NotImplementedError:
            raise RuntimeError(
                f"Tool '{lc_tool.name}' requires async execution; use execute_tool_async() instead"
            )

    async def _async_handler(args: Dict[str, Any]) -> Any:
        # Use ainvoke for async MCP tools
        if hasattr(lc_tool, "ainvoke"):
            return await lc_tool.ainvoke(args or {})
        else:
            raise RuntimeError(
                f"Tool '{lc_tool.name}' does not support async execution"
            )

    return ToolSpec(
        name=lc_tool.name,
        description=(lc_tool.description or "").strip() or f"MCP tool {lc_tool.name}",
        arguments_schema=_extract_args_schema(lc_tool),
        handler=_handler,
        source=f"mcp:{server_name}" if server_name else "mcp",
        async_handler=_async_handler,
    )


def register_mcp_tools(lc_tools: List[Any]) -> int:
    """Register MCP-discovered tools, replacing any previous MCP entries."""
    # Drop previous MCP-sourced tools
    for n in [k for k, v in _TOOLS.items() if v.source.startswith("mcp")]:
        _TOOLS.pop(n, None)

    added = 0
    for t in lc_tools:
        try:
            spec = _wrap_mcp_tool(t)
        except Exception as e:
            log.warning("Skipping MCP tool %r: %s", getattr(t, "name", "?"), e)
            continue
        if spec.name in _TOOLS:
            log.warning("Tool name collision for %r; MCP version wins", spec.name)
        _TOOLS[spec.name] = spec
        added += 1
    log.info("Registered %d MCP tool(s) into registry (total=%d)", added, len(_TOOLS))
    return added
