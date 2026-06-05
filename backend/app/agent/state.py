"""LangGraph agent state schema."""
from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class RetrievedDoc(TypedDict, total=False):
    text: str
    source: str
    score: float
    metadata: Dict[str, Any]


class ProposedAction(TypedDict, total=False):
    tool: str
    arguments: Dict[str, Any]
    rationale: str


class ToolResult(TypedDict, total=False):
    tool: str
    arguments: Dict[str, Any]
    output: Any
    error: Optional[str]


class AgentState(TypedDict, total=False):
    """State flowing through the LangGraph."""

    # Conversation history (LangGraph appends with add_messages reducer)
    messages: Annotated[List[BaseMessage], add_messages]

    # The latest user question (extracted from messages)
    question: str

    # Retrieved context from OpenSearch
    context: List[RetrievedDoc]

    # Phase 3 additions
    proposed_action: Optional[ProposedAction]
    approved: Optional[bool]
    tool_result: Optional[ToolResult]

    # Final assistant answer text (also appended to messages)
    answer: Optional[str]

