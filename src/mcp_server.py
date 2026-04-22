# ClawBrain MCP Server - Standardized Memory Interface
import asyncio
import logging
import httpx
import os
from typing import Any, Dict, List, Optional
from mcp.server import Server
from mcp.types import Tool, Resource, TextContent
from src.memory.router import MemoryRouter

logger = logging.getLogger("GATEWAY.MCP")

def create_mcp_server(mr: Optional[MemoryRouter] = None, remote_url: Optional[str] = None) -> Server:
    server = Server("ClawBrain")

    async def get_context(session_id: str, query: str, budget: int) -> str:
        if remote_url:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(f"{remote_url}/v1/query", json={
                        "query": query, 
                        "session_id": session_id, 
                        "budget": budget
                    })
                    if resp.status_code == 200:
                        return resp.json().get("context", "(No relevant memory found)")
                    return f"(Remote Query Error: {resp.status_code})"
            except Exception as e:
                return f"(Remote Connection Error: {e})"
        
        if mr:
            return await mr.get_combined_context(session_id, query, max_chars=budget)
        return "(Memory Engine Offline)"

    async def do_ingest(session_id: str, fact: str) -> str:
        if remote_url:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(f"{remote_url}/v1/ingest", json={
                        "content": fact, 
                        "session_id": session_id
                    })
                    if resp.status_code == 200:
                        return resp.json().get("trace_id", "unknown_remote_id")
                    return f"error_{resp.status_code}"
            except Exception as e:
                return f"connection_error_{str(e)[:20]}"
        
        if mr:
            stimulus = {"messages": [{"role": "user", "content": fact}]}
            return await mr.ingest(stimulus, session_id=session_id, sync_distill=False)
        return "engine_offline"

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            Tool(
                name="recall_memory",
                description="Query ClawBrain's Tri-Layer Memory (L1/L2/L3/Vault) for relevant context.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query or current focus."},
                        "session_id": {"type": "string", "description": "The session ID to isolate memory (default: 'default')."},
                        "budget": {"type": "integer", "description": "Maximum characters to return (default: 2000)."}
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="ingest_fact",
                description="Forcefully archive an important fact or realization into the memory stream.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "fact": {"type": "string", "description": "The fact to remember."},
                        "session_id": {"type": "string", "description": "The session ID (default: 'default')."}
                    },
                    "required": ["fact"]
                }
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        if name == "recall_memory":
            query = arguments.get("query")
            session_id = arguments.get("session_id", "default")
            budget = arguments.get("budget", 2000)
            
            context = await get_context(session_id, query, budget)
            return [TextContent(type="text", text=context)]
            
        elif name == "ingest_fact":
            fact = arguments.get("fact")
            session_id = arguments.get("session_id", "default")
            
            trace_id = await do_ingest(session_id, fact)
            return [TextContent(type="text", text=f"Fact archived. Trace ID: {trace_id}")]
            
        raise ValueError(f"Unknown tool: {name}")

    @server.list_resources()
    async def list_resources() -> List[Resource]:
        if remote_url:
            # Resource listing for remote mode is currently static or requires a new management endpoint
            return []
            
        if mr:
            sessions = list(mr._wm_sessions.keys())
            return [
                Resource(
                    uri=f"memory://neocortex/{sid}",
                    name=f"Semantic Summary ({sid})",
                    description=f"Live L3 summary for session {sid}",
                    mimeType="text/plain"
                ) for sid in sessions
            ]
        return []

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        if uri.startswith("memory://neocortex/"):
            session_id = uri.split("/")[-1]
            if mr:
                summary = mr.neo.get_summary(session_id)
                return summary or "(No summary available yet)"
            return "(Direct resource access unavailable in remote mode)"
        raise ValueError(f"Unknown resource: {uri}")

    return server

async def main():
    """Standalone entry point for Stdio transport (e.g. for Claude Desktop)."""
    from mcp.server.stdio import stdio_server
    
    # 1. Detection: Check if Gateway is already running
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_dir = os.getenv("CLAWBRAIN_DB_DIR", os.path.join(base_dir, "data"))
    gateway_url = os.getenv("CLAWBRAIN_URL", "http://localhost:11435")
    
    is_remote = False
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.get(f"{gateway_url}/health")
            if resp.status_code == 200:
                is_remote = True
                # Log to stderr because stdout is used for MCP JSON-RPC
                print(f"DEBUG: [MCP] Live Gateway detected at {gateway_url}. Operating in Thin Client mode.", file=sys.stderr)
    except:
        pass

    if is_remote:
        print(f"DEBUG: [MCP] Connecting to remote gateway at {gateway_url}", file=sys.stderr)
        server = create_mcp_server(remote_url=gateway_url)
    else:
        print(f"DEBUG: [MCP] Initializing local MemoryRouter...", file=sys.stderr)
        # v0.2.1: Disable heavy background tasks and wait for ready event
        mr = MemoryRouter(db_dir=db_dir, enable_room_detection=False, enable_cognitive_plane=False)
        await mr.wait_until_ready()
        server = create_mcp_server(mr=mr)
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    import sys
    asyncio.run(main())
