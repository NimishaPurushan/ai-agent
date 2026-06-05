"""Tests for MCP server config loading."""
import json
from pathlib import Path

from app.core.config import get_settings
from app.mcp import config as mcp_config


def test_load_server_configs_missing_returns_empty(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("MCP_SERVERS_CONFIG", "")
    assert mcp_config.load_server_configs() == {}


def test_load_server_configs_parses_stdio(tmp_path: Path, monkeypatch):
    cfg = {
        "servers": {
            "fs": {
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "./sandbox"],
                "env": {"FOO": "bar"},
            },
            "broken": {"transport": "stdio"},  # missing command → skipped
        }
    }
    p = tmp_path / "mcp.json"
    p.write_text(json.dumps(cfg))

    get_settings.cache_clear()
    monkeypatch.setenv("MCP_SERVERS_CONFIG", str(p))
    out = mcp_config.load_server_configs()
    assert "fs" in out and "broken" not in out
    assert out["fs"]["command"] == "npx"
    assert out["fs"]["env"] == {"FOO": "bar"}


def test_load_server_configs_parses_http(tmp_path: Path, monkeypatch):
    cfg = {"servers": {"remote": {"transport": "streamable_http", "url": "https://x/mcp"}}}
    p = tmp_path / "mcp.json"
    p.write_text(json.dumps(cfg))

    get_settings.cache_clear()
    monkeypatch.setenv("MCP_SERVERS_CONFIG", str(p))
    out = mcp_config.load_server_configs()
    assert out["remote"]["url"] == "https://x/mcp"

