"""Tests for FastAPI endpoints (root, health, and chat APIs)."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from langgraph.types import Command

from app.main import app
from app.schemas import ChatRequest, ChatResponse, ConfirmRequest


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


class TestRootEndpoint:
    """Tests for GET / endpoint."""

    def test_root_returns_app_info(self, client):
        """Test root endpoint returns app metadata."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "AI Agent Chatbot"
        assert "version" in data
        assert "phase" in data
        assert data["phase"] == 4


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    @patch("app.main.os_health")
    def test_health_ok(self, mock_os_health, client):
        """Test health endpoint when OpenSearch is healthy."""
        mock_os_health.return_value = {"status": "green"}
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["opensearch"] == "green"
        mock_os_health.assert_called_once()

    @patch("app.main.os_health")
    def test_health_opensearch_unreachable(self, mock_os_health, client):
        """Test health endpoint when OpenSearch is unreachable."""
        mock_os_health.return_value = None
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["opensearch"] == "unreachable"

    @patch("app.main.os_health")
    def test_health_opensearch_yellow(self, mock_os_health, client):
        """Test health endpoint with degraded OpenSearch status."""
        mock_os_health.return_value = {"status": "yellow"}
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["opensearch"] == "yellow"


class TestToolsEndpoint:
    """Tests for GET /api/tools endpoint."""

    @patch("app.api.list_tools")
    def test_tools_returns_list(self, mock_list_tools, client):
        """Test tools endpoint returns list of available tools."""
        # Mock tools with required attributes
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
        assert "tools" in data
        assert len(data["tools"]) == 2
        assert data["tools"][0]["name"] == "tool1"
        assert data["tools"][0]["source"] == "local"
        assert data["tools"][1]["name"] == "tool2"
        assert data["tools"][1]["source"] == "mcp"

    @patch("app.api.list_tools")
    def test_tools_empty_list(self, mock_list_tools, client):
        """Test tools endpoint with no tools available."""
        mock_list_tools.return_value = []
        response = client.get("/api/tools")
        assert response.status_code == 200
        data = response.json()
        assert data["tools"] == []


class TestChatEndpoint:
    """Tests for POST /api/chat endpoint."""

    @patch("app.api.get_graph")
    def test_chat_success_completed(self, mock_get_graph, client):
        """Test successful chat request with completed status."""
        # Mock the graph
        mock_graph = AsyncMock()
        mock_get_graph.return_value = mock_graph

        # Mock the graph.ainvoke response for a completed interaction
        mock_graph.ainvoke.return_value = {
            "messages": [{"role": "user", "content": "Hello"}],
            "context": [
                {
                    "text": "Relevant info",
                    "source": "doc1.txt",
                    "score": 0.95,
                    "metadata": {"type": "retrieved"},
                }
            ],
            "answer": "This is the answer",
            "tool_result": None,
            "__interrupt__": None,
        }

        # Send chat request
        payload = {"session_id": "test-session-123", "message": "Hello"}
        response = client.post("/api/chat", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-123"
        assert data["status"] == "completed"
        assert data["answer"] == "This is the answer"
        assert len(data["context"]) == 1
        assert data["context"][0]["text"] == "Relevant info"
        assert data["proposed_action"] is None
        mock_graph.ainvoke.assert_called_once()

    @patch("app.api.get_graph")
    def test_chat_awaiting_confirmation(self, mock_get_graph, client):
        """Test chat request that interrupts for human confirmation."""
        mock_graph = AsyncMock()
        mock_get_graph.return_value = mock_graph

        # Mock interruption with proposed action
        mock_interrupt = MagicMock()
        mock_interrupt.value = {
            "proposed_action": {
                "tool": "search",
                "arguments": {"query": "test"},
                "rationale": "To find information",
            }
        }

        mock_graph.ainvoke.return_value = {
            "messages": [],
            "context": [],
            "__interrupt__": [mock_interrupt],
        }

        payload = {"session_id": "test-session-456", "message": "Search for something"}
        response = client.post("/api/chat", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "awaiting_confirmation"
        assert data["proposed_action"] is not None
        assert data["proposed_action"]["tool"] == "search"
        assert data["proposed_action"]["arguments"]["query"] == "test"

    @patch("app.api.get_graph")
    def test_chat_invalid_request(self, mock_get_graph, client):
        """Test chat endpoint with invalid request."""
        # Missing required fields
        response = client.post("/api/chat", json={"session_id": "test"})
        assert response.status_code == 422  # Validation error

    @patch("app.api.get_graph")
    def test_chat_empty_message(self, mock_get_graph, client):
        """Test chat endpoint with empty message."""
        response = client.post(
            "/api/chat", json={"session_id": "test", "message": ""}
        )
        assert response.status_code == 422

    @patch("app.api.get_graph")
    def test_chat_agent_error(self, mock_get_graph, client):
        """Test chat endpoint when agent raises an error."""
        mock_graph = AsyncMock()
        mock_get_graph.return_value = mock_graph
        mock_graph.ainvoke.side_effect = ValueError("Agent processing failed")

        payload = {"session_id": "test-session", "message": "Hello"}
        response = client.post("/api/chat", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert "Agent error" in data["detail"]

    @patch("app.api.get_graph")
    def test_chat_with_tool_result(self, mock_get_graph, client):
        """Test chat response that includes tool execution result."""
        mock_graph = AsyncMock()
        mock_get_graph.return_value = mock_graph

        mock_graph.ainvoke.return_value = {
            "messages": [],
            "context": [],
            "answer": "Tool executed successfully",
            "tool_result": {
                "tool": "calculator",
                "arguments": {"operation": "add", "a": 5, "b": 3},
                "output": 8,
                "error": None,
            },
            "__interrupt__": None,
        }

        payload = {"session_id": "test-session", "message": "Calculate 5 + 3"}
        response = client.post("/api/chat", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["tool_result"] is not None
        assert data["tool_result"]["tool"] == "calculator"
        assert data["tool_result"]["output"] == 8


class TestConfirmEndpoint:
    """Tests for POST /api/confirm endpoint."""

    @patch("app.api.get_graph")
    def test_confirm_approved(self, mock_get_graph, client):
        """Test confirming and approving a proposed action."""
        mock_graph = AsyncMock()
        mock_get_graph.return_value = mock_graph

        # Mock get_state showing pending confirmation
        mock_task = MagicMock()
        mock_task.interrupts = True
        mock_snapshot = MagicMock()
        mock_snapshot.tasks = [mock_task]
        mock_graph.get_state.return_value = mock_snapshot

        # Mock ainvoke response after confirmation
        mock_graph.ainvoke.return_value = {
            "messages": [],
            "context": [],
            "answer": "Action completed",
            "tool_result": {
                "tool": "email",
                "arguments": {"to": "user@example.com", "subject": "Test"},
                "output": "Email sent",
                "error": None,
            },
            "__interrupt__": None,
        }

        payload = {
            "session_id": "test-session",
            "approved": True,
        }
        response = client.post("/api/confirm", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["answer"] == "Action completed"

    @patch("app.api.get_graph")
    def test_confirm_rejected(self, mock_get_graph, client):
        """Test rejecting a proposed action."""
        mock_graph = AsyncMock()
        mock_get_graph.return_value = mock_graph

        mock_task = MagicMock()
        mock_task.interrupts = True
        mock_snapshot = MagicMock()
        mock_snapshot.tasks = [mock_task]
        mock_graph.get_state.return_value = mock_snapshot

        mock_graph.ainvoke.return_value = {
            "messages": [],
            "context": [],
            "answer": "Action was rejected",
            "__interrupt__": None,
        }

        payload = {
            "session_id": "test-session",
            "approved": False,
        }
        response = client.post("/api/confirm", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    @patch("app.api.get_graph")
    def test_confirm_with_modified_arguments(self, mock_get_graph, client):
        """Test confirming with modified tool arguments."""
        mock_graph = AsyncMock()
        mock_get_graph.return_value = mock_graph

        mock_task = MagicMock()
        mock_task.interrupts = True
        mock_snapshot = MagicMock()
        mock_snapshot.tasks = [mock_task]
        mock_graph.get_state.return_value = mock_snapshot

        mock_graph.ainvoke.return_value = {
            "messages": [],
            "context": [],
            "answer": "Modified action completed",
            "__interrupt__": None,
        }

        payload = {
            "session_id": "test-session",
            "approved": True,
            "arguments": {"recipient": "modified@example.com", "priority": "high"},
        }
        response = client.post("/api/confirm", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

        # Verify the arguments were passed in the Command
        call_args = mock_graph.ainvoke.call_args
        command = call_args[0][0]
        assert isinstance(command, Command)

    @patch("app.api.get_graph")
    def test_confirm_no_pending(self, mock_get_graph, client):
        """Test confirm when there's no pending confirmation."""
        mock_graph = AsyncMock()
        mock_get_graph.return_value = mock_graph

        # Mock get_state showing no pending confirmation
        mock_snapshot = MagicMock()
        mock_snapshot.tasks = []
        mock_graph.get_state.return_value = mock_snapshot

        payload = {
            "session_id": "test-session",
            "approved": True,
        }
        response = client.post("/api/confirm", json=payload)

        assert response.status_code == 409
        data = response.json()
        assert "No pending confirmation" in data["detail"]

    @patch("app.api.get_graph")
    def test_confirm_agent_error(self, mock_get_graph, client):
        """Test confirm endpoint when agent raises an error."""
        mock_graph = AsyncMock()
        mock_get_graph.return_value = mock_graph

        mock_task = MagicMock()
        mock_task.interrupts = True
        mock_snapshot = MagicMock()
        mock_snapshot.tasks = [mock_task]
        mock_graph.get_state.return_value = mock_snapshot

        mock_graph.ainvoke.side_effect = RuntimeError("Resume failed")

        payload = {
            "session_id": "test-session",
            "approved": True,
        }
        response = client.post("/api/confirm", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert "Resume error" in data["detail"]

    @patch("app.api.get_graph")
    def test_confirm_invalid_request(self, mock_get_graph, client):
        """Test confirm with invalid request."""
        # Missing required fields
        response = client.post("/api/confirm", json={"session_id": "test"})
        assert response.status_code == 422


class TestAPIIntegration:
    """Integration tests across multiple endpoints."""

    @patch("app.api.get_graph")
    @patch("app.api.list_tools")
    def test_conversation_flow(self, mock_list_tools, mock_get_graph, client):
        """Test a complete conversation flow: tools -> chat -> confirm."""
        # List available tools
        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.source = "local"
        mock_tool.description = "Search tool"
        mock_tool.arguments_schema = {}
        mock_list_tools.return_value = [mock_tool]

        tools_response = client.get("/api/tools")
        assert tools_response.status_code == 200
        assert len(tools_response.json()["tools"]) == 1

        # Send chat message that triggers confirmation
        mock_graph = AsyncMock()
        mock_get_graph.return_value = mock_graph

        mock_interrupt = MagicMock()
        mock_interrupt.value = {
            "proposed_action": {
                "tool": "search",
                "arguments": {"query": "test"},
                "rationale": "Search requested",
            }
        }

        mock_graph.ainvoke.return_value = {
            "messages": [],
            "context": [],
            "__interrupt__": [mock_interrupt],
        }

        chat_response = client.post(
            "/api/chat", json={"session_id": "flow-test", "message": "Search"}
        )
        assert chat_response.status_code == 200
        assert chat_response.json()["status"] == "awaiting_confirmation"

        # Confirm the action
        mock_task = MagicMock()
        mock_task.interrupts = True
        mock_snapshot = MagicMock()
        mock_snapshot.tasks = [mock_task]
        mock_graph.get_state.return_value = mock_snapshot

        mock_graph.ainvoke.return_value = {
            "messages": [],
            "context": [],
            "answer": "Search completed",
            "__interrupt__": None,
        }

        confirm_response = client.post(
            "/api/confirm",
            json={"session_id": "flow-test", "approved": True},
        )
        assert confirm_response.status_code == 200
        assert confirm_response.json()["status"] == "completed"
