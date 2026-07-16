"""
Simple MCP HTTP Server - provides tools accessible via HTTP at localhost:9000
Run with: python mcp_server.py
"""
import asyncio
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("simple-mcp-server")


# Register some example tools
@server.list_tools()
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
                    "to": {
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
                "required": ["to", "subject", "body"]
            }
        )
    ]


@server.call_tool()
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
        result = await _send_email(arguments)
        return [TextContent(type="text", text=result)]
    
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ============================================================================
# Email Sending Helper
# ============================================================================

async def _send_email(arguments: dict[str, Any]) -> str:
    """Send email using SMTP configuration from environment variables."""
    return  _generate_email(arguments)



async def main():
    """Run the MCP server with stdio transport for HTTP gateway."""
    async with stdio_server(server) as streams:
        await streams.read_to_close()

def _generate_email(arguments: dict[str, Any]) -> str:
    """Send email using SMTP configuration from environment variables."""
    try:
        # Get email parameters
        to_email = arguments.get("to", "").strip()
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
        
        return f"Email sent successfully to {recipient_list}\nSubject: {subject}"
    
    except smtplib.SMTPAuthenticationError:
        return "Error: SMTP authentication failed. Check SMTP_USER and SMTP_PASSWORD."
    except smtplib.SMTPException as e:
        return f"Error: SMTP error occurred: {str(e)}"
    except Exception as e:
        return f"Error: Failed to send email: {str(e)}"

if __name__ == "__main__":
    asyncio.run(main())
