"""
HTTP Gateway for MCP Server - exposes MCP server via HTTP at localhost:9000
Supports the streamable HTTP protocol expected by langchain-mcp-adapters

Run with: python mcp_http_server.py
"""
import asyncio
import json
import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from mcp.server import Server
from mcp.types import Tool, TextContent
import uvicorn

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="MCP HTTP Server")

# Create MCP server instance
mcp_server = Server("simple-mcp-server")


# ============================================================================
# MCP Tool Definitions
# ============================================================================

@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="get_weather",
            description="Get weather information for a location",
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or coordinates"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature unit"
                    }
                },
                "required": ["location"]
            }
        ),
        Tool(
            name="search_web",
            description="Search the web for information",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="calculate",
            description="Perform mathematical calculations",
            inputSchema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression (e.g., '2 + 2 * 3')"
                    }
                },
                "required": ["expression"]
            }
        ),
        Tool(
            name="send_email",
            description="Send an email to specified recipient(s)",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipient": {
                        "type": "string",
                        "description": "Email recipient(s) - comma-separated for multiple recipients"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject"
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content (can be plain text or HTML)"
                    },
                    "cc": {
                        "type": "string",
                        "description": "CC recipient(s) - comma-separated (optional)"
                    },
                    "is_html": {
                        "type": "boolean",
                        "description": "Whether the body is HTML (default: false)",
                        "default": False
                    }
                },
                "required": ["recipient", "subject", "body"]
            }
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    
    if name == "get_weather":
        location = arguments.get("location", "Unknown")
        unit = arguments.get("unit", "celsius")
        result = f"Weather for {location}: 22°{unit[0].upper()} with partly cloudy skies"
        return [TextContent(type="text", text=result)]
    
    elif name == "search_web":
        query = arguments.get("query", "")
        max_results = arguments.get("max_results", 5)
        result = f"Found {max_results} results for '{query}':\n1. Result 1\n2. Result 2\n3. Result 3"
        return [TextContent(type="text", text=result)]
    
    elif name == "calculate":
        expression = arguments.get("expression", "0")
        try:
            result = eval(expression)
            return [TextContent(type="text", text=f"Result: {result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    elif name == "send_email":
        return [TextContent(type="text", text=await _send_email(arguments))]
    
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ============================================================================
# Email Sending Helper
# ============================================================================

async def _send_email(arguments: dict[str, Any]) -> str:
    """Send email using SMTP configuration from environment variables."""
    try:
        # Get email parameters
        to_email = arguments.get("recipient", "").strip()
        subject = arguments.get("subject", "").strip()
        body = arguments.get("body", "").strip()
        cc_email = arguments.get("cc", "").strip()
        is_html = arguments.get("is_html", False)
        
        if not to_email or not subject or not body:
            return "Error: Missing required fields (to, subject, body)"
        
        # Get SMTP configuration from environment variables
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = os.getenv("SMTP_PORT", "587")
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")
        sender_email = os.getenv("SENDER_EMAIL", smtp_user)
        
        if not smtp_host or not smtp_user or not smtp_password:
            return "Error: SMTP configuration not set. Please set SMTP_HOST, SMTP_USER, and SMTP_PASSWORD environment variables."
        
        # Create email message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = to_email
        
        if cc_email:
            msg["Cc"] = cc_email
        
        # Attach body with appropriate content type
        content_type = "html" if is_html else "plain"
        msg.attach(MIMEText(body, content_type))
        
        # Send email
        try:
            smtp_port = int(smtp_port)
        except ValueError:
            return "Error: Invalid SMTP_PORT value"
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            
            # Combine recipients
            recipients = [addr.strip() for addr in to_email.split(",")]
            if cc_email:
                recipients.extend([addr.strip() for addr in cc_email.split(",")])
            
            server.sendmail(sender_email, recipients, msg.as_string())
        
        recipient_list = to_email
        if cc_email:
            recipient_list += f" (CC: {cc_email})"
        
        result = f"Email sent successfully to {recipient_list}\nSubject: {subject}"
        logger.info(result)
        return result
    
    except smtplib.SMTPAuthenticationError:
        return "Error: SMTP authentication failed. Check SMTP_USER and SMTP_PASSWORD."
    except smtplib.SMTPException as e:
        return f"Error: SMTP error occurred: {str(e)}"
    except Exception as e:
        logger.exception("Error sending email")
        return f"Error: Failed to send email: {str(e)}"


# ============================================================================
# HTTP Endpoints
# ============================================================================

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "server": "mcp-http-gateway"}


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """MCP protocol endpoint - handles all MCP requests."""
    try:
        body = await request.json()
        logger.info(f"MCP Request: {body.get('method', 'unknown')}")
        
        # Handle initialize request
        if body.get("method") == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "simple-mcp-server",
                        "version": "1.0.0"
                    }
                }
            }
        
        # Handle tools/list request
        if body.get("method") == "tools/list":
            tools = await list_tools()
            return {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema
                        }
                        for tool in tools
                    ]
                }
            }
        
        # Handle tools/call request
        if body.get("method") == "tools/call":
            tool_name = body.get("params", {}).get("name", "")
            tool_args = body.get("params", {}).get("arguments", {})
            
            result = await call_tool(tool_name, tool_args)
            return {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {
                    "content": [{"type": "text", "text": result[0].text}]
                }
            }
        
        # Unknown method
        return {
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "error": {
                "code": -32601,
                "message": f"Method not found: {body.get('method')}"
            }
        }
    
    except Exception as e:
        logger.exception("Error handling MCP request")
        return {
            "jsonrpc": "2.0",
            "id": -1,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }


if __name__ == "__main__":
    logger.info("Starting MCP HTTP Server on http://localhost:9000")
    uvicorn.run(app, host="0.0.0.0", port=9000, log_level="info")
