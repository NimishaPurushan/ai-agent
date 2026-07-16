"""Chat + Confirm API endpoints — Phase 3."""
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.agent.graph import get_graph
from app.agent.tools import list_tools
from app.core.logging import get_logger
from app.schemas import (
    ChatRequest,
    ChatResponse,
    ConfirmRequest,
    ProposedActionOut,
    RetrievedDocOut,
    ToolResultOut,
)

log = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


def _config_for(session_id: str) -> Dict[str, Any]:
    return {"configurable": {"thread_id": session_id}}


def _build_response(session_id: str, state: Dict[str, Any]) -> ChatResponse:
    interrupts = state.get("__interrupt__") or []
    if interrupts:
        intr = interrupts[0]
        value = getattr(intr, "value", intr) if not isinstance(intr, dict) else intr
        proposed = (value or {}).get("proposed_action") if isinstance(value, dict) else None
        return ChatResponse(
            session_id=session_id,
            status="awaiting_confirmation",
            context=[RetrievedDocOut(**d) for d in state.get("context", [])],
            proposed_action=ProposedActionOut(**proposed) if proposed else None,
        )

    tool_result = state.get("tool_result")
    return ChatResponse(
        session_id=session_id,
        status="completed",
        answer=state.get("answer", ""),
        context=[RetrievedDocOut(**d) for d in state.get("context", [])],
        tool_result=ToolResultOut(**tool_result) if tool_result else None,
    )


@router.get("/tools")
async def tools() -> Dict[str, Any]:
    """List all currently registered tools (local + MCP)."""
    return {
        "tools": [
            {
                "name": t.name,
                "source": t.source,
                "description": t.description,
                "arguments": t.arguments_schema,
            }
            for t in list_tools()
        ]
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    graph = get_graph()
    config = _config_for(req.session_id)
    try:
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=req.message)]},
            config=config,
        )
    except Exception as e:  # pragma: no cover
        log.exception("Agent failure")
        raise HTTPException(status_code=500, detail=f"Agent error: {e}") from e
    return _build_response(req.session_id, result)


@router.post("/confirm", response_model=ChatResponse)
async def confirm(req: ConfirmRequest) -> ChatResponse:
    graph = get_graph()
    config = _config_for(req.session_id)

    snapshot = graph.get_state(config)
    pending = any(getattr(t, "interrupts", None) for t in (snapshot.tasks or []))
    if not pending:
        raise HTTPException(
            status_code=409,
            detail="No pending confirmation for this session.",
        )

    resume_payload: Dict[str, Any] = {"approved": req.approved}
    if req.arguments is not None:
        resume_payload["arguments"] = req.arguments

    try:
        result = await graph.ainvoke(Command(resume=resume_payload), config=config)
    except Exception as e:  # pragma: no cover
        log.exception("Resume failure")
        raise HTTPException(status_code=500, detail=f"Resume error: {e}") from e
    return _build_response(req.session_id, result)
