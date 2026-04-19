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
        stderr=subprocess.PIPE
    )

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
    
    async with sse_client(url) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            # 1. Initialize
            await session.initialize()
            
            # 2. List Tools
            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            assert "recall_memory" in tool_names
            assert "ingest_fact" in tool_names
            
            # 3. Call Ingest Tool
            session_id = "mcp-audit-session"
            await session.call_tool("ingest_fact", {"fact": "The MCP canary is RED-FOX-5", "session_id": session_id})
            
            # 4. Call Recall Tool (Use strong semantic signal)
            res = await session.call_tool("recall_memory", {"query": "RED-FOX-5", "session_id": session_id})
            assert len(res.content) > 0
            assert "RED-FOX-5" in res.content[0].text
            
            # 5. List Resources (After ingestion, session should be active)
            resources = await session.list_resources()
            uris = [str(r.uri) for r in resources.resources] # Convert AnyUrl to string
            assert f"memory://neocortex/{session_id}" in uris
