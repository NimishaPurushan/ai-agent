# AI Agent Chatbot

LangGraph + OpenAI chatbot with OpenSearch vector retrieval, human-in-the-loop confirmation, and MCP tools.
See [PROJECT_PLAN.md](./PROJECT_PLAN.md).

## Phase 1 — Quick Start

### 1. Start infrastructure
```powershell
docker compose up -d
```
- OpenSearch:           http://localhost:9200
- OpenSearch Dashboards: http://localhost:5601
- Redis:                localhost:6379

### 2. Backend
```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1   # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -e .
Copy-Item .env.example .env    # then edit OPENAI_API_KEY
python -m app.vectorstore.ingest   # create index + load sample docs
uvicorn app.main:app --reload
```
Backend runs at http://localhost:8000 — health check: `GET /health`.

### 2b. (Optional) Configure MCP servers
Copy the example and edit it:
```powershell
Copy-Item backend/mcp_servers.example.json backend/mcp_servers.json
```
Then set `MCP_SERVERS_CONFIG=./mcp_servers.json` in `backend/.env` (already set in `.env.example`).
The default examples need Node (`npx`) and/or `uvx` installed.
Verify tools after backend boot: `GET http://localhost:8000/api/tools`.

### 2c. (Optional) Enable LangSmith monitoring

Create a LangSmith project and API key, then add these values to `backend/.env`:

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_replace-me
LANGSMITH_PROJECT=ai-agent-dev
```

LangGraph runs, LLM calls, and node execution will then appear in LangSmith. Each chat session is attached as trace metadata so its turns can be grouped in the LangSmith UI. Prompts, retrieved context, and tool outputs may be recorded; set `LANGSMITH_HIDE_INPUTS=true` and/or `LANGSMITH_HIDE_OUTPUTS=true` when that data should not leave the application.

### 3. Frontend
```powershell
cd frontend
npm install
npm run dev
```
Frontend runs at http://localhost:5173.
