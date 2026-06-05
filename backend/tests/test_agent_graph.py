"""Integration tests for the LangGraph — Phase 3 (confirm path)."""
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.agent import nodes
from app.agent.graph import build_graph
from app.agent.nodes import PlanSchema


def _llm_mock(structured_plan: PlanSchema, final_answer: str):
    """Return a mock ChatOpenAI whose .with_structured_output(...) yields the plan
    and whose .invoke(...) returns the final answer."""
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke.return_value = structured_plan
    llm.with_structured_output.return_value = structured
    llm.invoke.return_value = AIMessage(content=final_answer)
    return llm


def _common_patches(plan: PlanSchema, answer: str):
    return (
        patch.object(nodes, "knn_search", return_value=[{"text": "ctx", "source": "x.md"}]),
        patch.object(nodes, "get_embeddings", return_value=MagicMock(embed_query=lambda _q: [0.0] * 8)),
        patch.object(nodes, "get_chat_llm", return_value=_llm_mock(plan, answer)),
    )


def test_graph_no_tool_path_completes():
    plan = PlanSchema(use_tool=False, rationale="ctx is enough")
    p1, p2, p3 = _common_patches(plan, "Here is your answer [x.md].")
    with p1, p2, p3:
        graph = build_graph(checkpointer=MemorySaver())
        cfg = {"configurable": {"thread_id": "t1"}}
        result = graph.invoke({"messages": [HumanMessage(content="What is X?")]}, config=cfg)
    assert result.get("answer", "").startswith("Here is your answer")
    assert "__interrupt__" not in result or not result["__interrupt__"]


def test_graph_tool_path_pauses_then_resumes_approved():
    plan = PlanSchema(use_tool=True, tool="echo", arguments={"text": "hello"}, rationale="user asked echo")
    p1, p2, p3 = _common_patches(plan, "Echoed for you.")
    with p1, p2, p3:
        graph = build_graph(checkpointer=MemorySaver())
        cfg = {"configurable": {"thread_id": "t2"}}

        # First call → interrupt for confirmation
        paused = graph.invoke({"messages": [HumanMessage(content="echo hello")]}, config=cfg)
        assert paused.get("__interrupt__"), "expected an interrupt"

        # Resume with approval
        done = graph.invoke(Command(resume={"approved": True}), config=cfg)

    assert done["tool_result"]["tool"] == "echo"
    assert done["tool_result"]["output"] == {"echo": "hello"}
    assert "Echoed" in done["answer"]


def test_graph_tool_path_declined_skips_execution():
    plan = PlanSchema(use_tool=True, tool="echo", arguments={"text": "nope"}, rationale="user asked echo")
    p1, p2, p3 = _common_patches(plan, "Okay, skipped the tool.")
    with p1, p2, p3:
        graph = build_graph(checkpointer=MemorySaver())
        cfg = {"configurable": {"thread_id": "t3"}}

        paused = graph.invoke({"messages": [HumanMessage(content="echo nope")]}, config=cfg)
        assert paused.get("__interrupt__")

        done = graph.invoke(Command(resume={"approved": False}), config=cfg)

    assert done.get("tool_result") is None
    assert "skipped" in done["answer"].lower()
