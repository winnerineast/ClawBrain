# Generated from design/management_api.md v1.1

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🦞 ClawBrain Management Dashboard</title>
    <style>
        :root {
            --bg: #0d1117;
            --sidebar: #161b22;
            --card: #21262d;
            --text: #c9d1d9;
            --accent: #58a6ff;
            --danger: #f85149;
            --success: #3fb950;
            --border: #30363d;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            display: flex;
            height: 100 vh;
        }
        #sidebar {
            width: 250px;
            background-color: var(--sidebar);
            border-right: 1px solid var(--border);
            padding: 20px;
            overflow-y: auto;
        }
        #main {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
        }
        h1, h2 { color: var(--accent); }
        .session-item {
            padding: 10px;
            border-radius: 6px;
            cursor: pointer;
            margin-bottom: 5px;
            border: 1px solid transparent;
        }
        .session-item:hover { background-color: var(--card); }
        .session-item.active { 
            background-color: var(--accent); 
            color: white; 
        }
        .card {
            background-color: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
        }
        pre {
            background: #000;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
            white-space: pre-wrap;
            font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace;
            font-size: 12px;
        }
        .controls {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        button {
            padding: 8px 16px;
            border-radius: 6px;
            border: 1px solid var(--border);
            background: var(--sidebar);
            color: var(--text);
            cursor: pointer;
        }
        button:hover { background: var(--card); }
        .btn-danger { color: var(--danger); border-color: var(--danger); }
        .btn-success { color: var(--success); border-color: var(--success); }
        .trace-item {
            border-bottom: 1px solid var(--border);
            padding: 10px 0;
        }
        .timestamp { font-size: 0.8em; color: #8b949e; }
        .tag {
            font-size: 10px;
            padding: 2px 6px;
            border-radius: 10px;
            background: var(--border);
            margin-right: 5px;
        }
    </style>
</head>
<body>
    <div id="sidebar">
        <h2>Sessions</h2>
        <button onclick="loadSessions()">Refresh List</button>
        <div id="session-list" style="margin-top: 20px;"></div>
    </div>
    <div id="main">
        <div id="welcome" style="text-align: center; margin-top: 100px;">
            <h1>🦞 ClawBrain Dashboard</h1>
            <p>Select a session to inspect the AI's internal memory state.</p>
        </div>
        <div id="dashboard-content" style="display: none;">
            <h1 id="active-session-id">Session: ...</h1>
            
            <div class="controls">
                <button class="btn-success" onclick="triggerDistill()">🚀 Trigger Distillation (L3)</button>
                <button class="btn-danger" onclick="clearMemory()">🗑️ Clear Memory</button>
            </div>

            <div class="card">
                <h3>🧠 Neocortex (L3 - Semantic Summary)</h3>
                <div id="l3-content"><pre>Loading...</pre></div>
            </div>

            <div class="card">
                <h3>💭 Working Memory (L1 - Active Focus)</h3>
                <div id="l1-content"><pre>Loading...</pre></div>
            </div>

            <div class="card">
                <h3>📜 Interaction Traces (L2 - Hippocampus)</h3>
                <div id="l2-content">Loading...</div>
            </div>
        </div>
    </div>

    <script>
        let currentSession = null;

        async function loadSessions() {
            const resp = await fetch('/v1/management/sessions');
            const data = await resp.json();
            const list = document.getElementById('session-list');
            list.innerHTML = '';
            data.sessions.forEach(sid => {
                const div = document.createElement('div');
                div.className = 'session-item' + (sid === currentSession ? ' active' : '');
                div.textContent = sid;
                div.onclick = () => selectSession(sid);
                list.appendChild(div);
            });
        }

        async function selectSession(sid) {
            currentSession = sid;
            document.getElementById('welcome').style.display = 'none';
            document.getElementById('dashboard-content').style.display = 'block';
            document.getElementById('active-session-id').textContent = 'Session: ' + sid;
            
            // Highlight sidebar
            document.querySelectorAll('.session-item').forEach(el => {
                el.classList.toggle('active', el.textContent === sid);
            });

            refreshAll();
        }

        async function refreshAll() {
            if (!currentSession) return;
            
            // Load Memory State (L1/L3)
            const mResp = await fetch(`/v1/memory/${currentSession}`);
            const mData = await mResp.json();
            document.getElementById('l3-content').innerHTML = `<pre>${mData.neocortex_summary || 'No summary generated yet.'}</pre>`;
            document.getElementById('l1-content').innerHTML = `<pre>${JSON.stringify(mData.working_memory_preview, null, 2)}</pre>`;

            // Load Traces (L2)
            const tResp = await fetch(`/v1/management/traces/${currentSession}?limit=20`);
            const tData = await tResp.json();
            const container = document.getElementById('l2-content');
            container.innerHTML = '';
            tData.traces.forEach(t => {
                const div = document.createElement('div');
                div.className = 'trace-item';
                const time = new Date(t.timestamp * 1000).toLocaleString();
                div.innerHTML = `
                    <div class="timestamp">${time} <span class="tag">${t.model}</span></div>
                    <pre>${t.raw_content}</pre>
                `;
                container.appendChild(div);
            });
        }

        async function triggerDistill() {
            if (!currentSession) return;
            await fetch(`/v1/memory/${currentSession}/distill`, {method: 'POST'});
            alert('Distillation triggered.');
        }

        async function clearMemory() {
            if (!currentSession || !confirm('Really clear all memory for this session?')) return;
            await fetch(`/v1/memory/${currentSession}`, {method: 'DELETE'});
            refreshAll();
        }

        // Initial load
        loadSessions();
        // Auto refresh
        setInterval(refreshAll, 10000);
    </script>
</body>
</html>
"""
