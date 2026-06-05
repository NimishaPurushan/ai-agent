"""Pydantic schemas for the chat + confirm API."""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Client-supplied session id (uuid)")
    message: str = Field(..., min_length=1)


class RetrievedDocOut(BaseModel):
    text: str
    source: Optional[str] = None
    score: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class ProposedActionOut(BaseModel):
    tool: str
    arguments: Dict[str, Any] = {}
    rationale: str = ""


class ToolResultOut(BaseModel):
    tool: str
    arguments: Dict[str, Any] = {}
    output: Any = None
    error: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    status: Literal["completed", "awaiting_confirmation"]
    answer: Optional[str] = None
    context: List[RetrievedDocOut] = []
    proposed_action: Optional[ProposedActionOut] = None
    tool_result: Optional[ToolResultOut] = None


class ConfirmRequest(BaseModel):
    session_id: str
    approved: bool
    arguments: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional override for the tool arguments before execution.",
    )
