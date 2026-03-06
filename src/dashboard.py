"""
dashboard.py — iEarn.Bot Local Dashboard
Runs at http://localhost:7799
"""
import os, json
from pathlib import Path
from flask import Flask, jsonify, render_template_string
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
BASE = Path(__file__).parent.parent

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
    .badge{font-size:.72rem;font-weight:700;padding:.2rem .6rem;border-radius:99px}
    .badge.on{background:rgba(34,197,94,.15);color:var(--green)} .badge.off{background:rgba(100,116,139,.15);color:var(--subtle)}
    .log{font-family:'JetBrains Mono',monospace;font-size:.8rem;color:var(--subtle);line-height:1.8;max-height:200px;overflow-y:auto}
    .dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--green);margin-right:.5rem;animation:pulse 2s infinite}
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
    <div class="kpi"><div class="kpi-label">Active Strategies</div><div class="kpi-val" id="strategies">0</div></div>
    <div class="kpi"><div class="kpi-label">SkillPay Balance</div><div class="kpi-val" id="balance">— USDT</div></div>
  </div>

  <div class="section">
    <h2>STRATEGIES</h2>
    <div class="strategy"><span class="strat-name">V1 — BTC Momentum</span><span class="badge on">Active</span></div>
    <div class="strategy"><span class="strat-name">V2 — Leaderboard Copy</span><span class="badge on">Active</span></div>
    <div class="strategy"><span class="strat-name">V3 — Wallet Tracking</span><span class="badge off">Inactive</span></div>
  </div>

  <div class="section">
    <h2>RECENT LOGS</h2>
    <div class="log" id="logs">Loading logs...</div>
  </div>

  <script>
    async function refresh() {
      try {
        const r = await fetch('/api/status');
        const d = await r.json();
        document.getElementById('pnl').textContent = (d.pnl >= 0 ? '+' : '') + '$' + d.pnl.toFixed(2);
        document.getElementById('pnl').className = 'kpi-val ' + (d.pnl >= 0 ? 'green' : 'red');
        document.getElementById('positions').textContent = d.positions;
        document.getElementById('strategies').textContent = d.active_strategies;
        document.getElementById('balance').textContent = d.skillpay_balance + ' USDT';
      } catch(e) {}
      try {
        const r = await fetch('/api/logs');
        const d = await r.json();
        document.getElementById('logs').innerHTML = d.lines.map(l => `<div>${l}</div>`).join('');
      } catch(e) {}
    }
    refresh();
    setInterval(refresh, 10000);
  </script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/status")
def status():
    try:
        from skillpay import check_balance
        bal = check_balance()
    except:
        bal = 0.0
    # Read positions from data dir
    pos_dir = BASE / "data" / "positions"
    positions = len(list(pos_dir.glob("*.json"))) if pos_dir.exists() else 0
    strategies_dir = BASE / "data" / "strategies"
    strategies = len(list(strategies_dir.glob("V*.json"))) if strategies_dir.exists() else 0
    return jsonify({"pnl": 0.0, "positions": positions, "active_strategies": strategies, "skillpay_balance": round(bal, 4)})

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
