"""Unit tests for LangGraph nodes (mocked LLM + vector store)."""
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from app.agent import nodes
from app.agent.nodes import PlanSchema


def test_retrieve_context_extracts_question_and_calls_knn():
    fake_hits = [
        {"text": "doc one", "source": "a.md", "score": 0.91},
        {"text": "doc two", "source": "b.md", "score": 0.80},
    ]
    with patch.object(nodes, "knn_search", return_value=fake_hits) as mk_knn, \
         patch.object(nodes, "get_embeddings") as mk_emb:
        mk_emb.return_value.embed_query.return_value = [0.0] * 8
        state = {"messages": [HumanMessage(content="What is OpenSearch?")]}
        out = nodes.retrieve_context(state)

    assert out["question"] == "What is OpenSearch?"
    assert out["context"] == fake_hits
    mk_knn.assert_called_once()


def test_plan_action_no_tool():
    with patch.object(nodes, "get_chat_llm") as mk_llm:
        structured = MagicMock()
        structured.invoke.return_value = PlanSchema(use_tool=False, rationale="context is enough")
        mk_llm.return_value.with_structured_output.return_value = structured
        out = nodes.plan_action({"question": "what is opensearch?", "context": []})
    assert out["proposed_action"] is None


def test_plan_action_with_tool():
    with patch.object(nodes, "get_chat_llm") as mk_llm:
        structured = MagicMock()
        structured.invoke.return_value = PlanSchema(
            use_tool=True, tool="get_current_time", arguments={}, rationale="user asked time"
        )
        mk_llm.return_value.with_structured_output.return_value = structured
        out = nodes.plan_action({"question": "what time is it?", "context": []})
    assert out["proposed_action"]["tool"] == "get_current_time"


def test_execute_tool_runs_registered_handler():
    state = {"proposed_action": {"tool": "echo", "arguments": {"text": "hi"}}}
    out = nodes.execute_tool(state)
    assert out["tool_result"]["output"] == {"echo": "hi"}
    assert out["tool_result"]["error"] is None


def test_execute_tool_unknown_returns_error():
    state = {"proposed_action": {"tool": "nope", "arguments": {}}}
    out = nodes.execute_tool(state)
    assert out["tool_result"]["error"] is not None


def test_generate_response_uses_llm_and_appends_message():
    state = {
        "question": "What is OpenSearch?",
        "context": [{"text": "OpenSearch is a search engine.", "source": "a.md"}],
        "messages": [HumanMessage(content="What is OpenSearch?")],
    }
    with patch.object(nodes, "get_chat_llm") as mk_llm:
        mk_llm.return_value.invoke.return_value = AIMessage(content="It's a search engine [a.md].")
        out = nodes.generate_response(state)
    assert "search engine" in out["answer"]
    assert isinstance(out["messages"][0], AIMessage)


def test_routers():
    assert nodes.route_after_plan({"proposed_action": {"tool": "x"}}) == "request_confirmation"
    assert nodes.route_after_plan({"proposed_action": None}) == "generate_response"
    assert nodes.route_after_confirmation({"approved": True}) == "execute_tool"
    assert nodes.route_after_confirmation({"approved": False}) == "generate_response"
