# MCP Server Regression Test
import pytest
import subprocess
import os
import time
import json
import httpx
import asyncio
import sys
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

@pytest.fixture(scope="module")
def mcp_server_instance():
    """Start a test server instance for MCP."""
    port = 11437
    db_dir = "tests/data/mcp_test_db"
    if os.path.exists(db_dir):
        import shutil
        shutil.rmtree(db_dir)
    os.makedirs(db_dir, exist_ok=True)

    # Find project root relative to this test file
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    uvicorn_path = os.path.join(project_root, "venv/bin/uvicorn")

    env = os.environ.copy()
    env["CLAWBRAIN_DB_DIR"] = os.path.join(project_root, db_dir)
    # Use the controlled test vault fixture
    env["CLAWBRAIN_VAULT_PATH"] = os.path.join(project_root, "tests/fixtures/test_vault")
    env["CLAWBRAIN_DISABLE_ROOM_DETECTION"] = "true"
    env["PYTHONPATH"] = project_root

    process = subprocess.Popen(
        [uvicorn_path, "src.main:app", "--host", "127.0.0.1", "--port", str(port)],
        env=env,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT # Merge stdout and stderr
    )

    # Function to print server logs in background
    def log_reader(proc):
        for line in iter(proc.stdout.readline, b''):
            print(f"[SERVER_LOG] {line.decode().strip()}")

    import threading
    log_thread = threading.Thread(target=log_reader, args=(process,), daemon=True)
    log_thread.start()

    # Wait for server AND cognitive engine to be ready (Conditional Wait)
    print("\n[WAIT] Waiting for server stability signal...")
    start_time = time.time()
    safety_limit = 300 # 5 minutes for slow hardware
    
    while time.time() - start_time < safety_limit:
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print(f"Server Crashed! STDERR: {stderr.decode() if stderr else 'None'}")
            pytest.fail("MCP Test Server crashed during startup")
            
        try:
            s_resp = httpx.get(f"http://127.0.0.1:{port}/v1/status", timeout=1.0)
            if s_resp.status_code == 200:
                status_data = s_resp.json()
                if status_data.get("status") == "online":
                    print(f"Success! Server reached ONLINE state in {int(time.time() - start_time)}s")
                    break
                else:
                    if int(time.time() - start_time) % 10 == 0:
                        print(f"  ...still initializing ({status_data.get('status')})...")
        except:
            pass
        time.sleep(2)
    else:
        process.terminate()
        pytest.fail(f"MCP Test Server failed to reach ONLINE status within {safety_limit}s safety limit")
        
    yield f"http://127.0.0.1:{port}"
    
    process.terminate()

@pytest.mark.asyncio
async def test_p38_mcp_full_handshake(mcp_server_instance):
    """Verify MCP Tool Discovery and Tool Calling."""
    url = f"{mcp_server_instance}/mcp/sse"
    print(f"\n[MCP_CLIENT] Connecting to SSE at {url}...")
    
    async with sse_client(url) as streams:
        print("[MCP_CLIENT] SSE streams opened. Creating session...")
        async with ClientSession(streams[0], streams[1]) as session:
            # 1. Initialize
            print("[MCP_CLIENT] Initializing session...")
            await session.initialize()
            print("[MCP_CLIENT] Session initialized.")
            
            # 2. List Tools
            print("[MCP_CLIENT] Listing tools...")
            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            print(f"[MCP_CLIENT] Found tools: {tool_names}")
            assert "recall_memory" in tool_names
            assert "ingest_fact" in tool_names
            
            # 3. Call Ingest Tool
            session_id = "mcp-audit-session"
            print(f"[MCP_CLIENT] Calling ingest_fact for {session_id}...")
            await session.call_tool("ingest_fact", {"fact": "The MCP canary is RED-FOX-5", "session_id": session_id})
            print("[MCP_CLIENT] ingest_fact finished.")
            
            # v0.2.1: Give the heartbeat a moment or at least ensure L2 is committed
            await asyncio.sleep(1.0)
            
            # 4. Call Recall Tool (Use strong semantic signal)
            print("[MCP_CLIENT] Calling recall_memory...")
            res = await session.call_tool("recall_memory", {"query": "RED-FOX-5", "session_id": session_id})
            print(f"[MCP_CLIENT] recall_memory response: {res.content[0].text[:50]}...")
            assert len(res.content) > 0
            assert "RED-FOX-5" in res.content[0].text
            
            # 5. List Resources (After ingestion, session should be active)
            print("[MCP_CLIENT] Listing resources...")
            resources = await session.list_resources()
            uris = [str(r.uri) for r in resources.resources] 
            print(f"[MCP_CLIENT] Found URIs: {uris}")
            assert f"memory://neocortex/{session_id}" in uris
