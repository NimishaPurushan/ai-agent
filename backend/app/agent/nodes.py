"""LangGraph nodes — Phase 3 adds plan_action, request_confirmation, execute_tool."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import interrupt
from pydantic import BaseModel, ConfigDict, Field

from app.agent.llm import get_chat_llm, get_embeddings
from app.agent.state import AgentState, ProposedAction, RetrievedDoc, ToolResult
from app.agent.tools import execute_tool as run_tool
from app.agent.tools import tools_catalog_for_prompt
from app.core.logging import get_logger
from app.vectorstore.client import knn_search

log = get_logger(__name__)

ANSWER_SYSTEM_PROMPT = (
    "You are a helpful AI assistant. Answer the user's question using ONLY the "
    "provided context when it is relevant. If a tool result is provided, "
    "incorporate it into the answer. Cite sources inline as [source]."
)

PLAN_SYSTEM_PROMPT = (
    "You are an action planner. Decide whether a tool from the catalog is "
    "required to answer the user's question.\n\n"
    "Tool catalog:\n{catalog}\n\n"
    "Rules:\n"
    "- If retrieved context already answers the question, set use_tool=false.\n"
    "- Only choose a tool whose description clearly matches the request.\n"
    "- Provide a short rationale.\n"
    "- Arguments must be a JSON object matching the tool's args."
)

TOP_K = 4


def _latest_user_question(state: AgentState) -> str:
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return state.get("question", "")


def _format_context(docs: List[RetrievedDoc]) -> str:
    if not docs:
        return "(no context found)"
    return "\n".join(
        f"[{d.get('source', f'doc{i}')}] {d.get('text', '').strip()}"
        for i, d in enumerate(docs, 1)
    )


def retrieve_context(state: AgentState) -> Dict[str, Any]:
    question = _latest_user_question(state)
    if not question:
        return {"question": "", "context": []}
    vector = get_embeddings().embed_query(question)
    hits: List[RetrievedDoc] = knn_search(vector, k=TOP_K)
    log.info("Retrieved %d docs for: %r", len(hits), question[:80])
    return {"question": question, "context": hits}


class PlanSchema(BaseModel):
    model_config = ConfigDict(json_schema_extra={"additionalProperties": False})

    use_tool: bool = Field(..., description="Whether a tool is required.")
    tool: Optional[str] = Field(None, description="Tool name from the catalog, if use_tool.")
    arguments: Dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field("", description="Why this decision was made.")


def plan_action(state: AgentState) -> Dict[str, Any]:
    """LLM decides whether a tool is needed; produces a structured plan."""
    question = state.get("question") or _latest_user_question(state)
    context = state.get("context", [])

    llm = get_chat_llm().with_structured_output(PlanSchema)
    prompt = [
        SystemMessage(content=PLAN_SYSTEM_PROMPT.format(catalog=tools_catalog_for_prompt())),
        SystemMessage(content=f"Retrieved context:\n{_format_context(context)}"),
        HumanMessage(content=question),
    ]
    plan: PlanSchema = llm.invoke(prompt)  # type: ignore[assignment]
    log.info("Plan: use_tool=%s tool=%s", plan.use_tool, plan.tool)

    if not plan.use_tool or not plan.tool:
        return {"proposed_action": None}
    return {
        "proposed_action": ProposedAction(
            tool=plan.tool,
            arguments=plan.arguments or {},
            rationale=plan.rationale or "",
        )
    }


def request_confirmation(state: AgentState) -> Dict[str, Any]:
    """Pause the graph and surface the proposed action to the user.

    Frontend resumes via /api/confirm, which calls graph.invoke(Command(resume=...)).
    Resume payload shape: {"approved": bool, "arguments"?: dict}
    """
    action = state.get("proposed_action")
    if not action:
        return {"approved": False}

    user_decision = interrupt(
        {"kind": "tool_confirmation", "proposed_action": action}
    )
    if isinstance(user_decision, dict):
        approved = bool(user_decision.get("approved"))
        if "arguments" in user_decision and isinstance(user_decision["arguments"], dict):
            action = {**action, "arguments": user_decision["arguments"]}
    else:
        approved = bool(user_decision)

    log.info("User decision: approved=%s tool=%s", approved, action.get("tool"))
    return {"approved": approved, "proposed_action": action}


def execute_tool(state: AgentState) -> Dict[str, Any]:
    action = state.get("proposed_action") or {}
    name = action.get("tool", "")
    args = action.get("arguments", {}) or {}
    try:
        output = run_tool(name, args)
        result: ToolResult = {"tool": name, "arguments": args, "output": output, "error": None}
        log.info("Tool '%s' executed", name)
    except Exception as e:
        log.exception("Tool '%s' failed", name)
        result = {"tool": name, "arguments": args, "output": None, "error": str(e)}
    return {"tool_result": result}


def generate_response(state: AgentState) -> Dict[str, Any]:
    question = state.get("question") or _latest_user_question(state)
    context = state.get("context", [])
    tool_result = state.get("tool_result")
    approved = state.get("approved")
    proposed = state.get("proposed_action")

    extra_sections: List[str] = []
    if tool_result is not None:
        extra_sections.append(f"Tool result (tool={tool_result.get('tool')}): {tool_result}")
    elif proposed and approved is False:
        extra_sections.append(
            f"Note: The user DECLINED running tool '{proposed.get('tool')}'. "
            "Answer without it and acknowledge the refusal briefly."
        )

    prompt = [
        SystemMessage(content=ANSWER_SYSTEM_PROMPT),
        SystemMessage(content=f"Context:\n{_format_context(context)}"),
    ]
    for s in extra_sections:
        prompt.append(SystemMessage(content=s))
    prompt.append(HumanMessage(content=question))

    response = get_chat_llm().invoke(prompt)
    answer = response.content if isinstance(response.content, str) else str(response.content)
    return {"answer": answer, "messages": [AIMessage(content=answer)]}


def route_after_plan(state: AgentState) -> str:
    return "request_confirmation" if state.get("proposed_action") else "generate_response"


def route_after_confirmation(state: AgentState) -> str:
    return "execute_tool" if state.get("approved") else "generate_response"
