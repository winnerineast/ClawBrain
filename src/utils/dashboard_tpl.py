# Generated from design/management_api.md v1.3

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🦞 ClawBrain Information Flow</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        :root {
            --bg: #0d1117;
            --sidebar: #161b22;
            --card: #21262d;
            --text: #c9d1d9;
            --accent: #58a6ff;
            --danger: #f85149;
            --success: #3fb950;
            --warning: #d29922;
            --border: #30363d;
            --plane-relay: #238636;
            --plane-cognitive: #8957e5;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            display: flex;
            height: 100vh;
            overflow: hidden;
        }
        #sidebar {
            width: 250px;
            background-color: var(--sidebar);
            border-right: 1px solid var(--border);
            padding: 20px;
            display: flex;
            flex-direction: column;
            overflow-y: auto;
        }
        #main {
            flex: 1;
            padding: 20px;
            display: flex;
            flex-direction: column;
            overflow-y: auto;
        }
        h1, h2, h3 { color: var(--accent); margin-top: 0; }
        .session-item {
            padding: 8px 12px;
            border-radius: 6px;
            cursor: pointer;
            margin-bottom: 4px;
            font-size: 13px;
            word-break: break-all;
            border: 1px solid transparent;
        }
        .session-item:hover { background-color: var(--card); }
        .session-item.active { background-color: var(--accent); color: white; }
        
        .card {
            background-color: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
        }
        
        #flow-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        #visual-flow {
            background: #fff;
            border-radius: 8px;
            padding: 10px;
            margin-bottom: 20px;
            min-height: 180px;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        
        #event-feed {
            flex: 1;
            display: flex;
            flex-direction: column;
            min-height: 0;
        }
        #event-list {
            flex: 1;
            overflow-y: auto;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: #000;
            padding: 10px;
        }
        .event-item {
            padding: 8px;
            border-bottom: 1px solid #222;
            font-size: 12px;
            display: flex;
            gap: 10px;
            cursor: pointer;
        }
        .event-item:hover { background: #111; }
        .event-time { color: #666; min-width: 80px; }
        .event-plane { 
            padding: 2px 6px; 
            border-radius: 4px; 
            font-weight: bold; 
            text-transform: uppercase;
            font-size: 10px;
            min-width: 60px;
            text-align: center;
        }
        .plane-relay { background: var(--plane-relay); color: white; }
        .plane-cognitive { background: var(--plane-cognitive); color: white; }
        .event-msg { flex: 1; }
        
        .btn-tab { 
            border: 1px solid var(--border); 
            background: var(--card); 
            color: var(--text); 
            padding: 5px 15px; 
            border-radius: 20px; 
            cursor: pointer; 
            font-size: 12px;
            margin-right: 5px;
        }
        .btn-tab.active { background: var(--accent); color: white; border-color: var(--accent); }
        .btn-success { background: var(--plane-relay); color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
        .btn-success:disabled { background: var(--border); cursor: not-allowed; }
        
        #xray-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.8);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        #xray-content {
            width: 80%;
            height: 80%;
            background: var(--bg);
            border: 1px solid var(--accent);
            border-radius: 12px;
            padding: 20px;
            display: flex;
            flex-direction: column;
        }
        pre {
            flex: 1;
            background: #000;
            padding: 15px;
            border-radius: 4px;
            overflow: auto;
            color: var(--success);
            font-family: ui-monospace, SFMono-Regular, monospace;
            font-size: 12px;
        }
        
        .status-pill {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 10px;
            background: var(--border);
        }
        .pulse { animation: pulse-red 2s infinite; }
        @keyframes pulse-red {
            0% { box-shadow: 0 0 0 0 rgba(248, 81, 73, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(248, 81, 73, 0); }
            100% { box-shadow: 0 0 0 0 rgba(248, 81, 73, 0); }
        }
    </style>
</head>
<body>
    <div id="sidebar">
        <h2>ClawBrain</h2>
        <div id="platform-info" class="card" style="padding: 10px; font-size: 11px;">
            Detecting platform...
        </div>
        
        <h3 style="margin-top: 20px; font-size: 16px;">Active Sessions</h3>
        <div id="session-list" style="flex: 1;"></div>
        <button onclick="loadSessions()" style="width: 100%; padding: 8px; margin-top: 10px; cursor: pointer;">Refresh Sessions</button>
    </div>

    <div id="main">
        <div id="flow-header">
            <h1 id="active-session-title">Select a Session</h1>
            <div id="global-status">
                <button class="btn-tab active" onclick="showTab('flow')">Flow Diagram</button>
                <button class="btn-tab" onclick="showTab('taste')">Taste & Personality</button>
                <span id="relay-status" class="status-pill">Relay Plane: --</span>
                <span id="cog-status" class="status-pill">Cognitive Plane: --</span>
            </div>
        </div>

        <!-- TAB: Flow Diagram -->
        <div id="tab-flow" class="tab-content">
            <div id="visual-flow" class="mermaid">
                graph LR
                    User((User)) -- Chat --> Relay[Relay Plane]
                    Relay -- Request Context --> Cognitive[Cognitive Plane]
                    Cognitive -- Semantic Memory --> Relay
                    Relay -- Enriched Prompt --> LLM((LLM))
                    Vault[(Obsidian Vault)] -- Offline Sync --> Cognitive
            </div>

            <div id="event-feed">
                <h3>Information Flow Log (Real-time)</h3>
                <div id="event-list">
                    <div style="color: #666; text-align: center; margin-top: 40px;">No events recorded yet. Start a chat or sync your vault.</div>
                </div>
            </div>
        </div>

        <!-- TAB: Taste & Personality -->
        <div id="tab-taste" class="tab-content" style="display: none;">
            <div class="card">
                <h3>🎭 Subjective Taste Profile (TasteGuard)</h3>
                <p style="font-size: 13px; color: #8b949e;">
                    This profile acts as a <strong>Belief Anchor</strong> for your AI. It dictates how the Cognitive Plane distills memories 
                    and how the Grounding Judge validates context. Use it to set architectural preferences, 
                    coding styles, or specific organizational values.
                </p>
                <textarea id="taste-input" style="width: 100%; height: 200px; background: #000; color: var(--success); border: 1px solid var(--border); border-radius: 4px; padding: 10px; font-family: monospace;"></textarea>
                <div style="margin-top: 15px;">
                    <button id="save-taste-btn" class="btn-success" onclick="saveTasteProfile()">💾 Save & Apply Profile</button>
                    <span id="taste-status" style="margin-left: 10px; font-size: 12px;"></span>
                </div>
            </div>
        </div>
    </div>

    <div id="xray-overlay" onclick="closeXRay()">
        <div id="xray-content" onclick="event.stopPropagation()">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h2 style="margin: 0;">🔍 Context X-Ray View</h2>
                <button onclick="closeXRay()">Close</button>
            </div>
            <pre id="xray-json"></pre>
        </div>
    </div>

    <script>
        let currentSession = null;
        let lastEventTimestamp = 0;
        let activeTab = 'flow';

        mermaid.initialize({ startOnLoad: true, theme: 'neutral', securityLevel: 'loose' });

        function showTab(tabId) {
            activeTab = tabId;
            document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
            document.getElementById('tab-' + tabId).style.display = 'block';
            
            document.querySelectorAll('.btn-tab').forEach(btn => {
                btn.classList.toggle('active', btn.getAttribute('onclick').includes(tabId));
            });
            
            if (tabId === 'taste') loadTasteProfile();
        }

        async function loadTasteProfile() {
            try {
                const resp = await fetch('/v1/management/config/taste');
                const data = await resp.json();
                document.getElementById('taste-input').value = data.taste_profile;
            } catch (e) { console.error('Failed to load taste profile', e); }
        }

        async function saveTasteProfile() {
            const btn = document.getElementById('save-taste-btn');
            const status = document.getElementById('taste-status');
            const newValue = document.getElementById('taste-input').value;
            
            btn.disabled = true;
            status.textContent = "⏳ Saving...";
            
            try {
                const resp = await fetch('/v1/management/config/taste', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({taste_profile: newValue})
                });
                if (resp.ok) {
                    status.textContent = "✅ Saved successfully!";
                    status.style.color = "var(--success)";
                } else {
                    status.textContent = "❌ Save failed";
                    status.style.color = "var(--danger)";
                }
            } catch (e) { 
                status.textContent = "❌ Error: " + e;
                status.style.color = "var(--danger)";
            } finally {
                btn.disabled = false;
                setTimeout(() => { status.textContent = ""; }, 3000);
            }
        }

        async function loadSessions() {
            try {
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
                if (!currentSession && data.sessions.length > 0) selectSession(data.sessions[0]);
            } catch (e) { console.error('Sessions failed', e); }
        }

        async function selectSession(sid) {
            currentSession = sid;
            lastEventTimestamp = 0; // Reset to show history for this session
            document.getElementById('active-session-title').textContent = "Session: " + sid;
            document.querySelectorAll('.session-item').forEach(el => {
                el.classList.toggle('active', el.textContent === sid);
            });
            document.getElementById('event-list').innerHTML = '';
            refresh();
        }

        async function refresh() {
            try {
                const cogResp = await fetch('/v1/management/cognitive/status');
                const cogData = await cogResp.json();
                
                document.getElementById('platform-info').innerHTML = `
                    <div><strong>OS:</strong> ` + (cogData.platform || 'Detected') + `</div>
                    <div><strong>Mode:</strong> <span style="color: var(--accent)">` + (cogData.integration_mode || 'Unknown') + `</span></div>
                    <div><strong>Heartbeat:</strong> ` + cogData.heartbeat_seconds + `s</div>
                `;
                
                const relayPill = document.getElementById('relay-status');
                relayPill.textContent = "Relay Plane: ACTIVE";
                relayPill.style.color = "var(--success)";
                
                const cogPill = document.getElementById('cog-status');
                cogPill.textContent = "Cognitive Plane: " + (cogData.circuit_breakers.heartbeat ? "STALLED" : "ACTIVE");
                cogPill.style.color = cogData.circuit_breakers.heartbeat ? "var(--danger)" : "var(--plane-cognitive)";
                if (cogData.circuit_breakers.heartbeat) cogPill.classList.add('pulse');
                else cogPill.classList.remove('pulse');

                const eResp = await fetch('/v1/management/events?limit=50' + (currentSession ? '&session_id=' + currentSession : ''));
                const eData = await eResp.json();
                const container = document.getElementById('event-list');
                
                if (eData.events.length > 0 && container.querySelector('div[style]')) {
                    container.innerHTML = '';
                }

                eData.events.forEach(ev => {
                    if (ev.timestamp <= lastEventTimestamp) return;
                    
                    const div = document.createElement('div');
                    div.className = 'event-item';
                    const time = new Date(ev.timestamp * 1000).toLocaleTimeString();
                    div.innerHTML = `
                        <div class="event-time">` + time + `</div>
                        <div class="event-plane plane-` + ev.plane.toLowerCase() + `">` + ev.plane + `</div>
                        <div class="event-msg">` + ev.message + `</div>
                    `;
                    
                    if (ev.type === 'ContextEnrichment') {
                        div.onclick = () => showXRay(ev.data.session_id);
                        div.style.borderLeft = "3px solid var(--accent)";
                        div.innerHTML += "<span style='color: var(--accent)'>[View X-Ray]</span>";
                    } else if (ev.type === 'DeepMining' || ev.type === 'DeepIndexing') {
                        div.style.borderLeft = "3px solid var(--plane-cognitive)";
                    }
                    
                    container.insertBefore(div, container.firstChild);
                    lastEventTimestamp = Math.max(lastEventTimestamp, ev.timestamp);
                });

            } catch (e) { console.error('Refresh failed', e); }
        }

        async function showXRay(sid) {
            const resp = await fetch('/v1/management/last_injection/' + sid);
            const data = await resp.json();
            document.getElementById('xray-json').textContent = JSON.stringify(data.payload || {error: "No injection found"}, null, 2);
            document.getElementById('xray-overlay').style.display = 'flex';
        }

        function closeXRay() {
            document.getElementById('xray-overlay').style.display = 'none';
        }

        loadSessions();
        setInterval(refresh, 3000);
    </script>
</body>
</html>
"""
