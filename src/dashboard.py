"""
dashboard.py — iEarn.Bot Local Dashboard
Runs at http://localhost:7799
"""
import os, json
from pathlib import Path
from flask import Flask, jsonify, render_template_string, request
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
BASE = Path(__file__).parent.parent

# In-memory strategy state (persisted to data/strategies/state.json)
_DEFAULT_STRATEGIES = {
    "v1": {"name": "V1 — BTC Momentum",      "enabled": True},
    "v2": {"name": "V2 — Leaderboard Copy",  "enabled": True},
    "v3": {"name": "V3 — Wallet Tracking",   "enabled": False},
}

def _state_file() -> Path:
    p = BASE / "data" / "strategies"
    p.mkdir(parents=True, exist_ok=True)
    return p / "state.json"

def _load_state() -> dict:
    f = _state_file()
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    return dict(_DEFAULT_STRATEGIES)

def _save_state(state: dict):
    _state_file().write_text(json.dumps(state, indent=2))


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>iEarn.Bot Dashboard</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=JetBrains+Mono&display=swap" rel="stylesheet"/>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    :root{--bg:#080c14;--bg2:#0d1220;--card:#131c2e;--border:#1e2d45;--accent:#f97316;--green:#22c55e;--red:#ef4444;--text:#f1f5f9;--subtle:#94a3b8}
    body{background:var(--bg);color:var(--text);font-family:'Inter',sans-serif;padding:2rem;min-height:100vh}
    h1{font-size:1.5rem;font-weight:800;margin-bottom:.25rem}
    .sub{color:var(--subtle);font-size:.9rem;margin-bottom:2rem}
    .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem;margin-bottom:2rem}
    .kpi{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:1.25rem 1.5rem}
    .kpi-label{font-size:.75rem;color:var(--subtle);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.5rem}
    .kpi-val{font-size:1.8rem;font-weight:800;font-family:'JetBrains Mono',monospace}
    .kpi-val.green{color:var(--green)} .kpi-val.red{color:var(--red)} .kpi-val.orange{color:var(--accent)}
    .section{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:1.5rem;margin-bottom:1rem}
    .section h2{font-size:1rem;font-weight:700;margin-bottom:1rem;color:var(--subtle)}
    .strategy{display:flex;justify-content:space-between;align-items:center;padding:.75rem 0;border-bottom:1px solid var(--border)}
    .strategy:last-child{border-bottom:none}
    .strat-name{font-weight:600;font-size:.95rem}
    .strat-right{display:flex;align-items:center;gap:.75rem}
    .badge{font-size:.72rem;font-weight:700;padding:.2rem .6rem;border-radius:99px}
    .badge.on{background:rgba(34,197,94,.15);color:var(--green)} .badge.off{background:rgba(100,116,139,.15);color:var(--subtle)}
    /* Toggle switch */
    .toggle{position:relative;display:inline-block;width:42px;height:24px}
    .toggle input{opacity:0;width:0;height:0}
    .slider{position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;background:#1e2d45;border-radius:24px;transition:.25s}
    .slider:before{position:absolute;content:"";height:18px;width:18px;left:3px;bottom:3px;background:var(--subtle);border-radius:50%;transition:.25s}
    input:checked + .slider{background:var(--green)}
    input:checked + .slider:before{transform:translateX(18px);background:#fff}
    .log{font-family:'JetBrains Mono',monospace;font-size:.8rem;color:var(--subtle);line-height:1.8;max-height:220px;overflow-y:auto}
    .dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--green);margin-right:.5rem;animation:pulse 2s infinite}
    .refresh-hint{font-size:.72rem;color:var(--subtle);margin-top:.5rem;text-align:right}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
    @media(max-width:640px){body{padding:1rem}}
  </style>
</head>
<body>
  <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:.25rem">
    <svg width="28" height="28" viewBox="0 0 42 48" fill="none"><path d="M22 3C16 9 8 16 8 26c0 11 8 19 17 19s17-8 17-19c0-7-4-13-9-17 0 7-3 11-7 13 2-5 0-12-4-19z" fill="#f97316"/></svg>
    <h1>iEarn.Bot</h1>
    <span style="font-size:.8rem;color:var(--subtle)"><span class="dot"></span>Running</span>
  </div>
  <div class="sub">Local Dashboard · <a href="https://iearn.bot" style="color:var(--accent);text-decoration:none">iearn.bot</a></div>

  <div class="kpis" id="kpis">
    <div class="kpi"><div class="kpi-label">Total P&L</div><div class="kpi-val green" id="pnl">+$0.00</div></div>
    <div class="kpi"><div class="kpi-label">Open Positions</div><div class="kpi-val orange" id="positions">0</div></div>
    <div class="kpi"><div class="kpi-label">Active Strategies</div><div class="kpi-val" id="active_strategies">0</div></div>
    <div class="kpi">
      <div class="kpi-label">SkillPay Balance</div>
      <div class="kpi-val" id="balance">— USDT</div>
    </div>
  </div>

  <div class="section">
    <h2>STRATEGIES</h2>
    <div id="strategy-list">Loading…</div>
  </div>

  <div class="section">
    <h2>RECENT LOGS</h2>
    <div class="log" id="logs">Loading logs...</div>
    <div class="refresh-hint" id="refresh-hint">Auto-refreshes every 10 s</div>
  </div>

  <script>
    let _strategies = {};

    async function toggleStrategy(id, enabled) {
      try {
        await fetch('/api/strategy/toggle', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({id, enabled})
        });
        await refreshStrategies();
      } catch(e) { console.error(e); }
    }

    function renderStrategies(strategies) {
      const container = document.getElementById('strategy-list');
      container.innerHTML = Object.entries(strategies).map(([id, s]) => `
        <div class="strategy">
          <span class="strat-name">${s.name}</span>
          <div class="strat-right">
            <span class="badge ${s.enabled ? 'on' : 'off'}">${s.enabled ? 'Active' : 'Inactive'}</span>
            <label class="toggle">
              <input type="checkbox" ${s.enabled ? 'checked' : ''}
                onchange="toggleStrategy('${id}', this.checked)"/>
              <span class="slider"></span>
            </label>
          </div>
        </div>
      `).join('');
    }

    async function refreshStrategies() {
      try {
        const r = await fetch('/api/strategies');
        const data = await r.json();
        _strategies = data.strategies;
        renderStrategies(_strategies);
        // update active count
        const active = Object.values(_strategies).filter(s => s.enabled).length;
        document.getElementById('active_strategies').textContent = active;
      } catch(e) {}
    }

    async function refreshStatus() {
      try {
        const r = await fetch('/api/status');
        const d = await r.json();
        document.getElementById('pnl').textContent = (d.pnl >= 0 ? '+' : '') + '$' + d.pnl.toFixed(2);
        document.getElementById('pnl').className = 'kpi-val ' + (d.pnl >= 0 ? 'green' : 'red');
        document.getElementById('positions').textContent = d.positions;
        // Balance display
        const bal = d.skillpay_balance;
        const balEl = document.getElementById('balance');
        if (typeof bal === 'number') {
          balEl.textContent = bal.toFixed(4) + ' USDT';
          balEl.className = 'kpi-val ' + (bal < 0.05 ? 'red' : bal < 0.5 ? 'orange' : 'green');
        } else {
          balEl.textContent = '— USDT';
          balEl.className = 'kpi-val';
        }
      } catch(e) {}
    }

    async function refreshLogs() {
      try {
        const r = await fetch('/api/logs');
        const d = await r.json();
        const el = document.getElementById('logs');
        el.innerHTML = d.lines.map(l => `<div>${l}</div>`).join('');
        el.scrollTop = el.scrollHeight;
      } catch(e) {}
    }

    async function refreshAll() {
      const hint = document.getElementById('refresh-hint');
      hint.textContent = 'Refreshing…';
      await Promise.all([refreshStatus(), refreshStrategies(), refreshLogs()]);
      hint.textContent = 'Last refresh: ' + new Date().toLocaleTimeString() + ' · Auto every 10 s';
    }

    refreshAll();
    setInterval(refreshAll, 10000);
  </script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/status")
def status():
    try:
        import sys
        sys.path.insert(0, str(BASE / "src"))
        from skillpay import check_balance
        bal = check_balance()
    except Exception:
        bal = 0.0

    pos_dir = BASE / "data" / "positions"
    positions = len(list(pos_dir.glob("*.json"))) if pos_dir.exists() else 0

    state = _load_state()
    active_strategies = sum(1 for s in state.values() if s.get("enabled"))

    return jsonify({
        "pnl": 0.0,
        "positions": positions,
        "active_strategies": active_strategies,
        "skillpay_balance": round(bal, 4),
    })


@app.route("/api/strategies")
def get_strategies():
    return jsonify({"strategies": _load_state()})


@app.route("/api/strategy/toggle", methods=["POST"])
def toggle_strategy():
    data = request.get_json(force=True) or {}
    strat_id = data.get("id", "").lower()
    enabled = bool(data.get("enabled", False))

    state = _load_state()
    if strat_id not in state:
        return jsonify({"error": f"Unknown strategy: {strat_id}"}), 404

    state[strat_id]["enabled"] = enabled
    _save_state(state)

    return jsonify({
        "ok": True,
        "id": strat_id,
        "enabled": enabled,
        "strategies": state,
    })


@app.route("/api/logs")
def logs():
    log_file = BASE / "data" / "logs" / "bot.log"
    if log_file.exists():
        lines = log_file.read_text().strip().split("\n")[-30:]
    else:
        lines = ["No logs yet. Bot will write logs here when running."]
    return jsonify({"lines": lines})


if __name__ == "__main__":
    print("🚀 iEarn.Bot Dashboard → http://localhost:7799")
    app.run(host="0.0.0.0", port=7799, debug=False)
