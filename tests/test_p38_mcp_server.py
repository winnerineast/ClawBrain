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

    # Wait for server AND cognitive engine to be ready
    start_time = time.time()
    while time.time() - start_time < 60:
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            st_out = stdout.decode() if stdout else "None"
            st_err = stderr.decode() if stderr else "None"
            print(f"Server Crashed! STDOUT: {st_out}")
            print(f"Server Crashed! STDERR: {st_err}")
            pytest.fail("MCP Test Server crashed during startup")
            
        try:
            h_resp = httpx.get(f"http://127.0.0.1:{port}/health", timeout=2.0)
            s_resp = httpx.get(f"http://127.0.0.1:{port}/v1/status", timeout=2.0)
            if h_resp.status_code == 200 and s_resp.status_code == 200:
                if s_resp.json().get("status") == "online":
                    break
        except:
            pass
        time.sleep(2)
    else:
        process.terminate()
        pytest.fail("MCP Test Server failed to reach ONLINE status in 60s")
        
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
