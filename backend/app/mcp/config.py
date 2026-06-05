"""Load MCP server connection configs from a JSON file.

File shape (matches `langchain-mcp-adapters` MultiServerMCPClient):
{
  "servers": {
    "<name>": {
      "transport": "stdio" | "streamable_http",
      "command": "npx",            # stdio only
      "args": ["..."],             # stdio only
      "env": {"KEY": "VAL"},       # optional
      "url": "https://..."         # streamable_http only
    }
  }
}
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


def load_server_configs() -> Dict[str, Dict[str, Any]]:
    """Return {server_name: connection_dict} ready for MultiServerMCPClient.

    Returns an empty dict if no config file is set or the file is missing.
    """
    s = get_settings()
    path = s.mcp_servers_config
    if not path or not os.path.exists(path):
        log.info("No MCP servers config found (path=%r)", path)
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        log.error("Failed to read MCP config %s: %s", path, e)
        return {}

    servers = raw.get("servers", {}) if isinstance(raw, dict) else {}
    out: Dict[str, Dict[str, Any]] = {}
    for name, cfg in servers.items():
        if not isinstance(cfg, dict):
            continue
        transport = cfg.get("transport", "stdio")
        entry: Dict[str, Any] = {"transport": transport}
        if transport == "stdio":
            if not cfg.get("command"):
                log.warning("MCP server %r missing 'command'; skipping", name)
                continue
            entry["command"] = cfg["command"]
            entry["args"] = list(cfg.get("args", []))
            if cfg.get("env"):
                entry["env"] = dict(cfg["env"])
        elif transport in ("streamable_http", "http", "sse"):
            if not cfg.get("url"):
                log.warning("MCP server %r missing 'url'; skipping", name)
                continue
            entry["url"] = cfg["url"]
            if cfg.get("headers"):
                entry["headers"] = dict(cfg["headers"])
        else:
            log.warning("MCP server %r has unsupported transport %r", name, transport)
            continue
        out[name] = entry

    log.info("Loaded %d MCP server config(s): %s", len(out), list(out.keys()))
    return out

