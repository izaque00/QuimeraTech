# quimera/api/dashboard.py
"""
Dashboard HTML para monitoramento em tempo real.

Servido estaticamente pela API. Conecta via WebSocket
para mostrar progresso de missões ao vivo.

Uso:
    Acessar http://localhost:8000/dashboard
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quimera Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0a1a; color: #e0e0e0; min-height: 100vh; }
        .header { background: linear-gradient(135deg, #1a1a3e, #0d0d2b); padding: 20px 40px; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #2a2a5e; }
        .header h1 { font-size: 24px; background: linear-gradient(90deg, #00d4ff, #7b2ff7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .stats { display: flex; gap: 20px; }
        .stat { background: #1a1a3e; padding: 10px 20px; border-radius: 8px; text-align: center; }
        .stat .value { font-size: 24px; font-weight: bold; color: #00d4ff; }
        .stat .label { font-size: 12px; color: #888; }
        .container { max-width: 1200px; margin: 20px auto; padding: 0 20px; }
        .section { margin-bottom: 30px; }
        .section h2 { color: #7b2ff7; margin-bottom: 15px; font-size: 18px; }
        .mission-card { background: #12122a; border: 1px solid #2a2a5e; border-radius: 10px; padding: 20px; margin-bottom: 15px; transition: border-color 0.3s; }
        .mission-card:hover { border-color: #7b2ff7; }
        .mission-card .id { color: #00d4ff; font-family: monospace; font-size: 14px; margin-bottom: 8px; }
        .mission-card .info { display: flex; gap: 20px; flex-wrap: wrap; }
        .mission-card .info span { font-size: 13px; color: #aaa; }
        .progress-bar { margin-top: 10px; height: 6px; background: #2a2a5e; border-radius: 3px; overflow: hidden; }
        .progress-fill { height: 100%; border-radius: 3px; transition: width 0.5s; }
        .progress-fill.queued { background: #555; }
        .progress-fill.running { background: linear-gradient(90deg, #00d4ff, #7b2ff7); }
        .progress-fill.completed { background: #00ff88; }
        .progress-fill.failed { background: #ff4444; }
        .badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold; text-transform: uppercase; }
        .badge.queued { background: #333; color: #aaa; }
        .badge.running { background: #1a3a5e; color: #00d4ff; }
        .badge.completed { background: #1a3e2a; color: #00ff88; }
        .badge.failed { background: #3e1a1a; color: #ff4444; }
        .empty { text-align: center; padding: 40px; color: #555; }
        .new-mission { background: #12122a; border: 1px dashed #2a2a5e; border-radius: 10px; padding: 20px; }
        .new-mission form { display: flex; gap: 10px; flex-wrap: wrap; }
        .new-mission input { background: #1a1a3e; border: 1px solid #2a2a5e; color: #e0e0e0; padding: 10px; border-radius: 6px; flex: 1; min-width: 150px; }
        .new-mission button { background: linear-gradient(90deg, #7b2ff7, #00d4ff); border: none; color: white; padding: 10px 24px; border-radius: 6px; cursor: pointer; font-weight: bold; }
        .new-mission button:hover { opacity: 0.9; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🧬 Quimera Dashboard</h1>
        <div class="stats">
            <div class="stat"><div class="value" id="statActive">0</div><div class="label">Ativas</div></div>
            <div class="stat"><div class="value" id="statCompleted">0</div><div class="label">Concluídas</div></div>
            <div class="stat"><div class="value" id="statFailed">0</div><div class="label">Falhas</div></div>
            <div class="stat"><div class="value" id="statUptime">0s</div><div class="label">Uptime</div></div>
        </div>
    </div>

    <div class="container">
        <div class="section">
            <h2>➕ Nova Missão</h2>
            <div class="new-mission">
                <form id="newMissionForm">
                    <input type="text" id="kernelPath" placeholder="Caminho do kernel" value="/usr/src/linux" required>
                    <input type="text" id="targetArch" placeholder="Arquitetura" value="aarch64">
                    <input type="number" id="maxIter" placeholder="Max iterações" value="10" min="1" max="100">
                    <input type="text" id="llmProvider" placeholder="LLM (opcional)">
                    <button type="submit">🚀 Lançar Missão</button>
                </form>
            </div>
        </div>

        <div class="section">
            <h2>📋 Missões Ativas</h2>
            <div id="missionsList"><div class="empty">Nenhuma missão ativa</div></div>
        </div>
    </div>

    <script>
        const API = '/api/v1';
        const missions = {};

        async function loadHealth() {
            try {
                const r = await fetch(API + '/health');
                const h = await r.json();
                document.getElementById('statUptime').textContent = Math.floor(h.uptime_seconds) + 's';
            } catch(e) {}
        }

        async function loadMissions() {
            try {
                const r = await fetch(API + '/missions?limit=50');
                const list = await r.json();
                let active = 0, completed = 0, failed = 0;
                const container = document.getElementById('missionsList');
                
                if (!list.length) {
                    container.innerHTML = '<div class="empty">Nenhuma missão ativa</div>';
                } else {
                    container.innerHTML = list.map(m => {
                        if (m.status === 'running' || m.status === 'queued' || m.status === 'compiling') active++;
                        else if (m.status === 'completed') completed++;
                        else if (m.status === 'failed') failed++;
                        
                        missions[m.mission_id] = m;
                        return `<div class="mission-card">
                            <div class="id">🔹 ${m.mission_id}</div>
                            <div class="info">
                                <span>📁 ${m.kernel_path || 'N/A'}</span>
                                <span>🏗️ ${m.target_arch || 'N/A'}</span>
                                <span><span class="badge ${m.status}">${m.status}</span></span>
                                ${m.current_step ? '<span>📍 ' + m.current_step + '</span>' : ''}
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill ${m.status}" style="width:${m.progress_pct || 0}%"></div>
                            </div>
                            ${m.error_message ? '<div style="color:#ff4444;margin-top:8px;font-size:12px;">⚠️ ' + m.error_message + '</div>' : ''}
                        </div>`;
                    }).join('');
                }
                
                document.getElementById('statActive').textContent = active;
                document.getElementById('statCompleted').textContent = completed;
                document.getElementById('statFailed').textContent = failed;
            } catch(e) { console.error(e); }
        }

        document.getElementById('newMissionForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = e.target.querySelector('button');
            btn.textContent = '⏳ Enviando...';
            btn.disabled = true;
            
            try {
                const r = await fetch(API + '/missions', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        kernel_path: document.getElementById('kernelPath').value,
                        target_arch: document.getElementById('targetArch').value,
                        max_iterations: parseInt(document.getElementById('maxIter').value),
                        llm_provider: document.getElementById('llmProvider').value || null,
                    })
                });
                if (r.ok) {
                    await loadMissions();
                    e.target.reset();
                    document.getElementById('kernelPath').value = '/usr/src/linux';
                    document.getElementById('targetArch').value = 'aarch64';
                    document.getElementById('maxIter').value = '10';
                }
            } catch(ex) { console.error(ex); }
            
            btn.textContent = '🚀 Lançar Missão';
            btn.disabled = false;
        });

        // Polling
        loadHealth();
        loadMissions();
        setInterval(loadHealth, 5000);
        setInterval(loadMissions, 3000);
    </script>
</body>
</html>"""
