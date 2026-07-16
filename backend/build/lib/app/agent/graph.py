"""LangGraph graph — Phase 3: retrieve → plan → (confirm → execute)? → respond."""
from functools import lru_cache

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    execute_tool,
    generate_response,
    plan_action,
    request_confirmation,
    retrieve_context,
    route_after_confirmation,
    route_after_plan,
)
from app.agent.state import AgentState


def build_graph(checkpointer=None):
    builder = StateGraph(AgentState)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("plan_action", plan_action)
    builder.add_node("request_confirmation", request_confirmation)
    builder.add_node("execute_tool", execute_tool)
    builder.add_node("generate_response", generate_response)



    builder.add_edge(START, "retrieve_context")
    builder.add_edge("retrieve_context", "plan_action")
    # builder.add_edge("plan_action", "execute_tool")

    builder.add_conditional_edges(
        "plan_action",
        route_after_plan,
        {
            "request_confirmation": "request_confirmation",
            "generate_response": "generate_response",
        },
    )
    builder.add_conditional_edges(
        "request_confirmation",
        route_after_confirmation,
        {
            "execute_tool": "execute_tool",
            "generate_response": "generate_response",
        },
    )
    # builder.add_edge("execute_tool", "generate_response")
    builder.add_edge("generate_response", END)

    return builder.compile(checkpointer=checkpointer)


@lru_cache
def get_checkpointer() -> MemorySaver:
    """In-memory checkpointer (no Redis). Swap for SqliteSaver to persist."""
    return MemorySaver()


@lru_cache
def get_graph():
    return build_graph(checkpointer=get_checkpointer())
