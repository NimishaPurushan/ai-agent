"""MCP client manager — discovers tools from configured MCP servers and
exposes them as LangChain BaseTool instances."""
from __future__ import annotations

import asyncio
from typing import List

from app.core.logging import get_logger
from app.mcp.config import load_server_configs

log = get_logger(__name__)

_cached_tools: List = []          # list of langchain_core.tools.BaseTool
_cached_client = None             # MultiServerMCPClient (kept alive for sessions)


async def load_mcp_tools_async() -> List:
    """Connect to all configured MCP servers and return LangChain tools."""
    global _cached_tools, _cached_client

    configs = load_server_configs()
    if not configs:
        _cached_tools = []
        return _cached_tools

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError as e:
        log.error("langchain-mcp-adapters not installed: %s", e)
        return []

    try:
        _cached_client = MultiServerMCPClient(configs)
        tools = await _cached_client.get_tools()
    except Exception as e:
        log.exception("Failed to initialize MCP client: %s", e)
        return []

    _cached_tools = list(tools)
    log.info("Discovered %d MCP tool(s): %s", len(_cached_tools), [t.name for t in _cached_tools])
    return _cached_tools


def load_mcp_tools() -> List:
    """Sync wrapper for use in startup."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Caller is already inside an event loop (e.g. FastAPI lifespan).
            # Schedule and wait via a new task is non-trivial; expect async caller.
            raise RuntimeError("load_mcp_tools called inside a running loop; use load_mcp_tools_async")
    except RuntimeError:
        pass
    return asyncio.run(load_mcp_tools_async())


def cached_mcp_tools() -> List:
    return list(_cached_tools)

