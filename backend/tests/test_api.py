"""Tests for FastAPI endpoints (root, health, and chat APIs)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from langgraph.types import Command

from app.api import _config_for
from app.main import app
from app.schemas import ChatRequest, ChatResponse, ConfirmRequest


@pytest.fixture
def client():
    return TestClient(app)


class TestRootEndpoint:
    def test_root_returns_app_info(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "AI Agent Chatbot"
        assert "version" in data
        assert "phase" in data
        assert data["phase"] == 4


class TestHealthEndpoint:
    @patch("app.main.os_health")
    def test_health_ok(self, mock_os_health, client):
        mock_os_health.return_value = {"status": "green"}
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["opensearch"] == "green"
        mock_os_health.assert_called_once()

    @patch("app.main.os_health")
    def test_health_opensearch_unreachable(self, mock_os_health, client):
        mock_os_health.return_value = None
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["opensearch"] == "unreachable"

    @patch("app.main.os_health")
    def test_health_opensearch_yellow(self, mock_os_health, client):
        mock_os_health.return_value = {"status": "yellow"}
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["opensearch"] == "yellow"


class TestToolsEndpoint:
    @patch("app.api.list_tools")
    def test_tools_returns_list(self, mock_list_tools, client):
        mock_tool1 = MagicMock()
        mock_tool1.name = "tool1"
        mock_tool1.source = "local"
        mock_tool1.description = "Tool 1 description"
        mock_tool1.arguments_schema = {"type": "object", "properties": {}}

        mock_tool2 = MagicMock()
        mock_tool2.name = "tool2"
        mock_tool2.source = "mcp"
        mock_tool2.description = "Tool 2 description"
        mock_tool2.arguments_schema = {"type": "object", "properties": {"param": "string"}}

        mock_list_tools.return_value = [mock_tool1, mock_tool2]

        response = client.get("/api/tools")
        assert response.status_code == 200
        data = response.json()
        assert len(data["tools"]) == 2
        assert data["tools"][0]["name"] == "tool1"
        assert data["tools"][1]["source"] == "mcp"

    @patch("app.api.list_tools")
    def test_tools_empty_list(self, mock_list_tools, client):
        mock_list_tools.return_value = []
        response = client.get("/api/tools")
        assert response.status_code == 200
        assert response.json()["tools"] == []


class TestLangSmithConfig:
    @patch("app.api.get_settings")
    def test_graph_config_includes_trace_metadata(self, mock_get_settings):
        mock_get_settings.return_value.app_env = "test"

        config = _config_for("session-123", "chat")

        assert config["configurable"] == {"thread_id": "session-123"}
        assert config["run_name"] == "api_chat"
        assert config["metadata"] == {
            "thread_id": "session-123",
            "environment": "test",
            "operation": "chat",
        }
        assert config["tags"] == ["ai-agent", "environment:test", "operation:chat"]


class TestChatEndpoint:
    @patch("app.api.get_graph")
    def test_chat_success_completed(self, mock_get_graph, client):
        mock_graph = AsyncMock()
        mock_get_graph.return_value = mock_graph
        mock_graph.ainvoke.return_value = {
            "messages": [{"role": "user", "content": "Hello"}],
            "context": [{"text": "Relevant info", "source": "doc1.txt", "score": 0.95, "metadata": {}}],
            "answer": "This is the answer",
            "tool_result": None,
            "__interrupt__": None,
        }

        response = client.post("/api/chat", json={"session_id": "test-session-123", "message": "Hello"})
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-123"
        assert data["status"] == "completed"
        assert data["answer"] == "This is the answer"
        assert data["context"][0]["text"] == "Relevant info"
        assert data["proposed_action"] is None

    @patch("app.api.get_graph")
    def test_chat_awaiting_confirmation(self, mock_get_graph, client):
        mock_graph = AsyncMock()
        mock_get_graph.return_value = mock_graph
        mock_interrupt = MagicMock()
        mock_interrupt.value = {
            "proposed_action": {"tool": "search", "arguments": {"query": "test"}, "rationale": "To find info"}
        }
        mock_graph.ainvoke.return_value = {
            "messages": [], "context": [], "__interrupt__": [mock_interrupt]
        }

        response = client.post("/api/chat", json={"session_id": "test-session-456", "message": "Search"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "awaiting_confirmation"
        assert data["proposed_action"]["tool"] == "search"

    @patch("app.api.get_graph")
    def test_chat_invalid_request(self, mock_get_graph, client):
        response = client.post("/api/chat", json={"session_id": "test"})
        assert response.status_code == 422

    @patch("app.api.get_graph")
    def test_chat_empty_message(self, mock_get_graph, client):
        response = client.post("/api/chat", json={"session_id": "test", "message": ""})
        assert response.status_code == 422

    @patch("app.api.get_graph")
    def test_chat_agent_error(self, mock_get_graph, client):
        mock_graph = AsyncMock()
        mock_get_graph.return_value = mock_graph
        mock_graph.ainvoke.side_effect = ValueError("Agent processing failed")

        response = client.post("/api/chat", json={"session_id": "test-session", "message": "Hello"})
        assert response.status_code == 500
        assert "Agent error" in response.json()["detail"]

    @patch("app.api.get_graph")
    def test_chat_with_tool_result(self, mock_get_graph, client):
        mock_graph = AsyncMock()
        mock_get_graph.return_value = mock_graph
        mock_graph.ainvoke.return_value = {
            "messages": [], "context": [],
            "answer": "Tool executed successfully",
            "tool_result": {"tool": "calculator", "arguments": {"operation": "add", "a": 5, "b": 3}, "output": 8, "error": None},
            "__interrupt__": None,
        }

        response = client.post("/api/chat", json={"session_id": "test-session", "message": "Calculate 5 + 3"})
        assert response.status_code == 200
        data = response.json()
        assert data["tool_result"]["tool"] == "calculator"
        assert data["tool_result"]["output"] == 8


def _make_pending_graph(ainvoke_return: dict) -> AsyncMock:
    """Helper: graph with a pending confirmation. get_state is SYNC (MagicMock)."""
    mock_graph = AsyncMock()

    mock_task = MagicMock()
    mock_task.interrupts = True
    mock_snapshot = MagicMock()
    mock_snapshot.tasks = [mock_task]

    # get_state is synchronous in LangGraph — use plain MagicMock, not AsyncMock
    mock_graph.get_state = MagicMock(return_value=mock_snapshot)
    mock_graph.ainvoke.return_value = ainvoke_return
    return mock_graph


class TestConfirmEndpoint:
    @patch("app.api.get_graph")
    def test_confirm_approved(self, mock_get_graph, client):
        mock_get_graph.return_value = _make_pending_graph({
            "messages": [], "context": [],
            "answer": "Action completed",
            "tool_result": {"tool": "email", "arguments": {}, "output": "Email sent", "error": None},
            "__interrupt__": None,
        })

        response = client.post("/api/confirm", json={"session_id": "test-session", "approved": True})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["answer"] == "Action completed"

    @patch("app.api.get_graph")
    def test_confirm_rejected(self, mock_get_graph, client):
        mock_get_graph.return_value = _make_pending_graph({
            "messages": [], "context": [], "answer": "Action was rejected", "__interrupt__": None,
        })

        response = client.post("/api/confirm", json={"session_id": "test-session", "approved": False})
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    @patch("app.api.get_graph")
    def test_confirm_with_modified_arguments(self, mock_get_graph, client):
        mock_get_graph.return_value = _make_pending_graph({
            "messages": [], "context": [], "answer": "Modified action completed", "__interrupt__": None,
        })

        response = client.post("/api/confirm", json={
            "session_id": "test-session", "approved": True,
            "arguments": {"recipient": "modified@example.com"},
        })
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

        call_args = mock_get_graph.return_value.ainvoke.call_args
        assert isinstance(call_args[0][0], Command)

    @patch("app.api.get_graph")
    def test_confirm_no_pending(self, mock_get_graph, client):
        mock_graph = AsyncMock()
        mock_get_graph.return_value = mock_graph
        mock_snapshot = MagicMock()
        mock_snapshot.tasks = []
        mock_graph.get_state = MagicMock(return_value=mock_snapshot)  # sync

        response = client.post("/api/confirm", json={"session_id": "test-session", "approved": True})
        assert response.status_code == 409
        assert "No pending confirmation" in response.json()["detail"]

    @patch("app.api.get_graph")
    def test_confirm_agent_error(self, mock_get_graph, client):
        mock_graph = AsyncMock()
        mock_get_graph.return_value = mock_graph
        mock_task = MagicMock()
        mock_task.interrupts = True
        mock_snapshot = MagicMock()
        mock_snapshot.tasks = [mock_task]
        mock_graph.get_state = MagicMock(return_value=mock_snapshot)  # sync
        mock_graph.ainvoke.side_effect = RuntimeError("Resume failed")

        response = client.post("/api/confirm", json={"session_id": "test-session", "approved": True})
        assert response.status_code == 500
        assert "Resume error" in response.json()["detail"]

    @patch("app.api.get_graph")
    def test_confirm_invalid_request(self, mock_get_graph, client):
        response = client.post("/api/confirm", json={"session_id": "test"})
        assert response.status_code == 422


class TestAPIIntegration:
    @patch("app.api.get_graph")
    @patch("app.api.list_tools")
    def test_conversation_flow(self, mock_list_tools, mock_get_graph, client):
        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.source = "local"
        mock_tool.description = "Search tool"
        mock_tool.arguments_schema = {}
        mock_list_tools.return_value = [mock_tool]

        tools_response = client.get("/api/tools")
        assert tools_response.status_code == 200
        assert len(tools_response.json()["tools"]) == 1

        mock_graph = AsyncMock()
        mock_get_graph.return_value = mock_graph

        mock_interrupt = MagicMock()
        mock_interrupt.value = {
            "proposed_action": {"tool": "search", "arguments": {"query": "test"}, "rationale": "Search requested"}
        }
        mock_graph.ainvoke.return_value = {
            "messages": [], "context": [], "__interrupt__": [mock_interrupt]
        }

        chat_response = client.post("/api/chat", json={"session_id": "flow-test", "message": "Search"})
        assert chat_response.status_code == 200
        assert chat_response.json()["status"] == "awaiting_confirmation"

        mock_task = MagicMock()
        mock_task.interrupts = True
        mock_snapshot = MagicMock()
        mock_snapshot.tasks = [mock_task]
        mock_graph.get_state = MagicMock(return_value=mock_snapshot)  # sync

        mock_graph.ainvoke.return_value = {
            "messages": [], "context": [], "answer": "Search completed", "__interrupt__": None,
        }

        confirm_response = client.post("/api/confirm", json={"session_id": "flow-test", "approved": True})
        assert confirm_response.status_code == 200
        assert confirm_response.json()["status"] == "completed"
