# Chatbot with Vector DB + MCP Tools — Project Plan

## 1. Overview
A conversational chatbot that:
1. Accepts user questions via a web UI.
2. Searches a vector database for relevant context.
3. Uses a LangGraph agent (OpenAI LLM) to interpret intent and propose tool actions.
4. Asks the user for confirmation before executing any action.
5. Executes MCP (Model Context Protocol) tools upon confirmation.
6. Streams the final response back to the UI.

## 2. Tech Stack
| Layer        | Technology                                    |
|--------------|-----------------------------------------------|
| Frontend     | React + Vite + TailwindCSS                    |
| Backend API  | FastAPI (Python 3.11+)                        |
| Agent        | LangGraph + LangChain                         |
| LLM          | OpenAI (gpt-4o / gpt-4o-mini)                 |
| Embeddings   | OpenAI `text-embedding-3-small`               |
| Vector DB    | Chroma (local) or Pinecone (cloud)            |
| Tools        | MCP servers (filesystem, custom domain tools) |
| State Store  | Redis (session + pending confirmations)       |
| Transport    | WebSocket (streaming) + REST                  |

## 3. High-Level Architecture
```
┌──────────────┐   WS/REST   ┌──────────────┐   ┌──────────────┐
│   Frontend   │ ──────────► │   FastAPI    │──►│  LangGraph   │
│   (React)    │ ◄────────── │   Backend    │   │    Agent     │
└──────────────┘             └──────┬───────┘   └──────┬───────┘
                                    │                  │
                          ┌─────────┼──────────┐       │
                          ▼         ▼          ▼       ▼
                      ┌───────┐ ┌──────┐  ┌────────┐ ┌──────┐
                      │ Redis │ │Vector│  │  MCP   │ │OpenAI│
                      │       │ │  DB  │  │ Tools  │ │ LLM  │
                      └───────┘ └──────┘  └────────┘ └──────┘
```

## 4. LangGraph Agent Nodes
1. `retrieve_context` — embed query, search vector DB, return top-k docs.
2. `plan_action` — LLM decides if an MCP tool is needed; produces an action plan.
3. `request_confirmation` — interrupts graph, sends plan to user, awaits reply.
4. `execute_tool` — runs MCP tool with arguments (only on approval).
5. `generate_response` — LLM composes final answer using context + tool result.
6. `END`

Use LangGraph's `interrupt()` + a local checkpointer (in-memory for dev, SQLite for persistence) for the human-in-the-loop confirmation step.

## 5. Project Structure
```
chatbot/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entrypoint
│   │   ├── api/
│   │   │   ├── chat.py          # /chat REST + WS endpoints
│   │   │   └── confirm.py       # /confirm endpoint
│   │   ├── agent/
│   │   │   ├── graph.py         # LangGraph definition
│   │   │   ├── nodes.py         # Node functions
│   │   │   └── state.py         # TypedDict state schema
│   │   ├── vectorstore/
│   │   │   ├── client.py        # Chroma/Pinecone wrapper
│   │   │   └── ingest.py        # Document ingestion script
│   │   ├── mcp/
│   │   │   ├── client.py        # MCP client manager
│   │   │   └── registry.py      # Tool registration
│   │   ├── core/
│   │   │   ├── config.py        # Settings (pydantic)
│   │   │   └── session.py       # Redis session store
│   │   └── schemas/
│   │       └── chat.py          # Pydantic models
│   ├── tests/
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatWindow.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   └── ConfirmationDialog.tsx
│   │   ├── hooks/
│   │   │   └── useChatSocket.ts
│   │   ├── api/
│   │   │   └── client.ts
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml
└── README.md
```

## 6. API Contract
### POST `/api/chat`
Request:
```json
{ "session_id": "uuid", "message": "string" }
```
Response (when confirmation needed):
```json
{
  "status": "awaiting_confirmation",
  "pending_id": "uuid",
  "proposed_action": {
    "tool": "filesystem.write_file",
    "arguments": { "path": "...", "content": "..." },
    "rationale": "string"
  }
}
```

### POST `/api/confirm`
```json
{ "session_id": "uuid", "pending_id": "uuid", "approved": true }
```

### WS `/ws/chat/{session_id}`
Streams token-level deltas + status events.

## 7. Implementation Phases

### Phase 1 — Foundations (Week 1)
- Scaffold backend (FastAPI) + frontend (Vite).
- Configure OpenAI, env management, logging.
- Stand up OpenSearch (Docker, k-NN plugin) + ingest sample docs.

### Phase 2 — Agent Core (Week 2)
- Implement LangGraph state + nodes (retrieve → respond).
- Wire OpenAI LLM and embeddings.
- Add unit tests for each node.

### Phase 3 — Human-in-the-loop (Week 3)
- Add `plan_action` + `request_confirmation` with `interrupt()`.
- Add Redis checkpointer for graph state.
- Implement `/confirm` endpoint to resume the graph.

### Phase 4 — MCP Integration (Week 4)
- Install `mcp` Python SDK.
- Connect to one or more MCP servers (stdio/HTTP).
- Map MCP tools into LangChain `Tool` objects.

### Phase 5 — Frontend Polish (Week 5)
- Chat UI with streaming.
- Confirmation modal showing proposed tool + args.
- Error handling, retries, history view.

### Phase 6 — Hardening (Week 6)
- Auth (JWT), rate limiting, observability (LangSmith).
- Dockerize, CI/CD, deploy.

## 8. Key Dependencies
```
langgraph>=0.2
langchain>=0.3
langchain-openai>=0.2
langchain-chroma>=0.1
mcp>=1.0
fastapi>=0.115
uvicorn[standard]
redis>=5
pydantic-settings
python-dotenv
```

## 9. Security & Safety
- Never auto-execute MCP tools without explicit user approval.
- Validate/whitelist tool names and argument schemas server-side.
- Store API keys in environment variables / secret manager.
- Sanitize and size-limit retrieved context before sending to LLM.
- Audit log every tool execution (who, what, when, result).

## 10. OpenSearch Configuration Notes
- Deploy via Docker (`opensearchproject/opensearch:2.x`) with `plugins.knn.enabled=true`.
- Create index with `index.knn: true` and a `knn_vector` field (dimension = 1536 for `text-embedding-3-small`).
- Recommended method: `hnsw` with `lucene` or `nmslib` engine; `space_type: cosinesimil`.
- Use LangChain's `OpenSearchVectorSearch` (`langchain_community.vectorstores`) for retriever integration.
- Secure with TLS + basic auth (or AWS SigV4 when using Amazon OpenSearch Service).
- Store config in `.env`: `OPENSEARCH_URL`, `OPENSEARCH_USER`, `OPENSEARCH_PASSWORD`, `OPENSEARCH_INDEX`.

## 11. Future Enhancements
- Multi-user auth + per-user vector namespaces.
- Tool usage analytics dashboard.
- Support for additional LLM providers (Anthropic, local models).
- Fine-grained "always allow / ask once" confirmation policies.

