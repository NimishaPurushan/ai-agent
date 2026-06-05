"""Tests for MCP tool wrapping into the registry."""
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel, Field

from app.agent import tools as tools_mod


class _EchoArgs(BaseModel):
    text: str = Field(..., description="Text to echo")


@pytest.fixture(autouse=True)
def _restore_registry():
    snapshot = dict(tools_mod._TOOLS)
    yield
    tools_mod._TOOLS.clear()
    tools_mod._TOOLS.update(snapshot)


def _fake_lc_tool(name: str, description: str, schema=_EchoArgs, return_value: Any = "ok"):
    t = MagicMock()
    t.name = name
    t.description = description
    t.args_schema = schema
    t.invoke = MagicMock(return_value=return_value)
    return t


def test_register_mcp_tools_adds_and_wraps():
    lc = _fake_lc_tool("mcp_echo", "Echo via MCP", return_value={"echoed": "hi"})
    added = tools_mod.register_mcp_tools([lc])
    assert added == 1

    spec = tools_mod.get_tool("mcp_echo")
    assert spec is not None
    assert spec.source.startswith("mcp")
    assert "text" in spec.arguments_schema

    result = tools_mod.execute_tool("mcp_echo", {"text": "hi"})
    assert result == {"echoed": "hi"}
    lc.invoke.assert_called_once_with({"text": "hi"})


def test_register_mcp_tools_clears_previous_mcp_entries():
    a = _fake_lc_tool("mcp_a", "A")
    b = _fake_lc_tool("mcp_b", "B")
    tools_mod.register_mcp_tools([a, b])
    assert tools_mod.get_tool("mcp_a") is not None

    # Re-register with just one tool → mcp_a should be gone
    c = _fake_lc_tool("mcp_c", "C")
    tools_mod.register_mcp_tools([c])
    assert tools_mod.get_tool("mcp_a") is None
    assert tools_mod.get_tool("mcp_c") is not None

    # Local tools should still be present
    assert tools_mod.get_tool("echo") is not None


def test_catalog_for_prompt_includes_source_tag():
    lc = _fake_lc_tool("mcp_x", "Do X")
    tools_mod.register_mcp_tools([lc])
    catalog = tools_mod.tools_catalog_for_prompt()
    assert "mcp_x [mcp]" in catalog or "mcp_x [mcp:" in catalog
    assert "echo [local]" in catalog

