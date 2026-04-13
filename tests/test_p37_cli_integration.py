# CLI Integration Regression Test
import pytest
import subprocess
import os
import time
import json
import httpx
from src.memory.storage import clear_chroma_clients

@pytest.fixture(scope="module")
def server_instance():
    """Start a test server instance."""
    # Ensure a clean slate for the test server
    port = 11436 # Use a different port for CLI tests to avoid collision
    db_dir = "tests/data/cli_test_db"
    if os.path.exists(db_dir):
        import shutil
        shutil.rmtree(db_dir)
    os.makedirs(db_dir, exist_ok=True)

    env = os.environ.copy()
    env["CLAWBRAIN_DB_DIR"] = db_dir
    # Use the controlled test vault fixture
    env["CLAWBRAIN_VAULT_PATH"] = os.path.join(os.getcwd(), "tests/fixtures/test_vault")
    env["CLAWBRAIN_DISABLE_ROOM_DETECTION"] = "true"
    env["PYTHONPATH"] = "."
    
    import sys
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", str(port)],
        env=env,
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
            pytest.fail("CLI Test Server crashed during startup")
            
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
        pytest.fail("CLI Test Server failed to reach ONLINE status in 60s")
        
    yield f"http://127.0.0.1:{port}"
    
    process.terminate()

def run_cli(command, base_url):
    env = os.environ.copy()
    env["CLAWBRAIN_URL"] = base_url
    result = subprocess.run(
        ["venv/bin/python", "src/cli.py"] + command,
        env=env,
        capture_output=True,
        text=True
    )
    return result

def test_p37_cli_full_cycle(server_instance):
    """Verify Ingest -> Query -> Status cycle via CLI."""
    session = "cli-canary-session"
    canary = "The CLI secret password is TRON-99"
    
    # 1. Ingest
    res = run_cli(["ingest", canary, "--session", session], server_instance)
    print(f"CLI Ingest Output: {res.stdout}")
    assert res.returncode == 0
    assert "Fact archived" in res.stdout
    
    # 2. Query
    res = run_cli(["query", "password", "--session", session], server_instance)
    print(f"CLI Query Output: {res.stdout}")
    assert res.returncode == 0
    assert "TRON-99" in res.stdout
    
    # 3. Status
    res = run_cli(["status"], server_instance)
    print(f"CLI Status Output: {res.stdout}")
    assert res.returncode == 0
    assert "ONLINE" in res.stdout
    assert session in res.stdout
