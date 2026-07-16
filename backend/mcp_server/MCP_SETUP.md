# MCP Server Setup Guide

## Overview

You now have:
1. **MCP HTTP Server** (`mcp_http_server.py`) - Provides tools via HTTP
2. **FastAPI Backend** (`app/main.py`) - Integrates with MCP server and langgraph
3. **Configuration** (`mcp_servers.json`) - Tells the backend where to find the MCP server

## How It Works

```
┌──────────────────┐
│  FastAPI Agent   │ (port 8000)
│  + LangGraph     │
└────────┬─────────┘
         │ connects to
         ▼
┌──────────────────┐
│  MCP HTTP Server │ (port 9000)
│  - get_weather   │
│  - search_web    │
│  - calculate     │
└──────────────────┘
```

## Running the Servers

### Option 1: Manual (Two Terminal Windows)

**Terminal 1 - MCP HTTP Server:**
```powershell
cd backend
python mcp_http_server.py
```

**Terminal 2 - FastAPI Backend:**
```powershell
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 2: Automated Script

**Using PowerShell (Recommended for your setup):**
```powershell
cd backend
.\run_servers.ps1
```

**Using Batch:**
```cmd
cd backend
run_servers.bat
```

## Verification

### Check MCP Server Health
```bash
curl http://localhost:9000/health
```

Expected response:
```json
{"status":"ok","server":"mcp-http-gateway"}
```

### Check FastAPI Backend
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status":"ok","opensearch":"..."}
```

### List Available Tools
```bash
curl http://localhost:8000/api/tools
```

This should now show:
- Local tools: `get_current_time`, `echo`, `word_count`
- MCP tools: `get_weather`, `search_web`, `calculate`

## Available Tools

### Local Tools
- **get_current_time**: Returns current UTC time
- **echo**: Echoes back provided text
- **word_count**: Counts words and characters

### MCP Tools (from HTTP Server)
- **get_weather**: Get weather for a location
  - Arguments: `location` (required), `unit` (optional: celsius/fahrenheit)
  
- **search_web**: Search the web
  - Arguments: `query` (required), `max_results` (optional: default 5)
  
- **calculate**: Perform math calculations
  - Arguments: `expression` (required, e.g., "2 + 2 * 3")

## Testing

### 1. Test Chat Endpoint
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session",
    "message": "What is the weather in Paris?"
  }'
```

The agent should:
1. Understand you want weather info
2. Plan to use the `get_weather` tool
3. Execute the tool and return a response

### 2. Test via Frontend
Visit `http://localhost:5173` (or your frontend port) and chat with the agent.

## Troubleshooting

### MCP Server won't start
- Ensure port 9000 is not in use: `netstat -ano | findstr :9000`
- Check Python is installed: `python --version`

### FastAPI can't connect to MCP Server
- Verify MCP server is running: `curl http://localhost:9000/health`
- Check `mcp_servers.json` has correct URL: `http://localhost:9000/mcp`
- Look at backend logs for errors

### Tools not appearing in `/api/tools`
- Check backend logs for MCP loading errors
- Restart both servers
- Verify MCP server `/mcp` endpoint responds to POST requests

## Extending the MCP Server

To add new tools, edit `mcp_http_server.py`:

1. Add tool definition to `list_tools()` function
2. Add tool handler to `call_tool()` function
3. Restart the MCP server

Example:
```python
Tool(
    name="my_tool",
    description="Do something useful",
    inputSchema={
        "type": "object",
        "properties": {
            "param": {"type": "string", "description": "A parameter"}
        },
        "required": ["param"]
    }
)
```

## Next Steps

1. Run both servers using the startup script
2. Test the `/api/tools` endpoint to see MCP tools
3. Test the chat endpoint with a message that triggers tool use
4. Extend with your own MCP tools as needed
