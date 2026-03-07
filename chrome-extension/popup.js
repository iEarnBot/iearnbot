// ── Config ────────────────────────────────────────────────────────────────
const CONFIG = {
  get serverUrl() { return localStorage.getItem('server_url') || 'http://localhost:7799' },
  proxyUrl: 'https://iearn.bot/api/chat',
  fetchUrl: 'https://iearn.bot/api/fetch-url',
}

let currentPage = 'dashboard'

// ── Router ────────────────────────────────────────────────────────────────
function switchTab(page) {
  currentPage = page
  document.querySelectorAll('.tab').forEach(t =>
    t.classList.toggle('active', t.dataset.page === page)
  )
  const pages = { dashboard: renderDashboard, strategy: renderStrategy, positions: renderPositions, settings: renderSettings }
  pages[page]?.()
}

// ── Dashboard ─────────────────────────────────────────────────────────────
function renderDashboard() {
  document.getElementById('content').innerHTML = `
    <div class="kpi-grid">
      <div class="kpi"><div class="kpi-label">Today P&L</div><div class="kpi-value green" id="todayPnl">+$0.00</div></div>
      <div class="kpi"><div class="kpi-label">Positions</div><div class="kpi-value" id="openPos">—</div></div>
      <div class="kpi"><div class="kpi-label">Win Rate</div><div class="kpi-value" id="winRate">—</div></div>
      <div class="kpi"><div class="kpi-label">Total P&L</div><div class="kpi-value" id="totalPnl">$0.00</div></div>
    </div>
    <div class="card">
      <div class="card-title">Active Strategies</div>
      <div id="strategyList"><div class="empty">🤖 Loading...</div></div>
    </div>
    <div class="btn-row">
      <button class="btn btn-danger" onclick="killSwitch()">🔴 Kill Switch</button>
      <button class="btn btn-ghost" onclick="refreshDashboard()">🔄 Refresh</button>
    </div>
  `
  refreshDashboard()
}

async function refreshDashboard() {
  try {
    const [bal, pos, sched] = await Promise.allSettled([
      apiCall('get_balances'), apiCall('get_positions'), apiCall('scheduler_status')
    ])

    if (bal.status === 'fulfilled' && bal.value?.usdc !== undefined) {
      document.getElementById('balanceDisplay').textContent = `$${Number(bal.value.usdc).toFixed(2)}`
      document.getElementById('statusDot').className = 'status-dot running'
    }
    if (pos.status === 'fulfilled' && pos.value?.positions) {
      document.getElementById('openPos').textContent = pos.value.positions.length
    }
    if (sched.status === 'fulfilled' && sched.value?.jobs) {
      const jobs = sched.value.jobs
      document.getElementById('strategyList').innerHTML = jobs.length
        ? jobs.map(j => `
          <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid #1e2d4540;font-size:.82rem">
            <span>${j.name || j.id}</span>
            <span class="badge ${j.status === 'running' ? 'badge-green' : 'badge-red'}">${j.status || 'idle'}</span>
          </div>`).join('')
        : '<div class="empty">🤖 No active strategies</div>'
    }
  } catch(e) {
    document.getElementById('statusDot').className = 'status-dot stopped'
    document.getElementById('strategyList').innerHTML = '<div class="empty">⚡ Cannot reach Mac mini</div>'
  }
}

// ── Strategy ──────────────────────────────────────────────────────────────
function renderStrategy() {
  document.getElementById('content').innerHTML = `
    <div class="card">
      <label class="label">📎 Article URL</label>
      <input type="url" id="articleUrl" class="input" placeholder="Paste X, YouTube, or any link..." />
      <button class="btn btn-ghost" onclick="fetchCurrentPage()" style="margin-bottom:8px">📄 Use Current Tab URL</button>
      <label class="label">Or paste text</label>
      <textarea id="articleText" class="input" placeholder="Paste article or describe strategy idea..."></textarea>
      <label class="label">Market</label>
      <select id="marketSelect" class="input">
        <option value="polymarket">Polymarket</option>
        <option value="kalshi">Kalshi</option>
        <option value="binance">Binance</option>
      </select>
      <button class="btn btn-primary" onclick="generateStrategy()" id="genBtn">✨ Generate Strategy</button>
    </div>
    <div id="strategyResult"></div>
  `
}

async function fetchCurrentPage() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
    if (tab?.url) {
      document.getElementById('articleUrl').value = tab.url
    }
  } catch(e) {}
}

async function generateStrategy() {
  const url = document.getElementById('articleUrl').value.trim()
  const text = document.getElementById('articleText').value.trim()
  const btn = document.getElementById('genBtn')
  btn.innerHTML = '<span class="spinner"></span> Generating...'
  btn.disabled = true

  try {
    let content = text
    if (url) {
      try {
        const r = await fetch(CONFIG.fetchUrl, {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ url })
        })
        const d = await r.json()
        if (d.ok) content = d.content + '\n' + text
      } catch(e) {}
    }

    const r = await fetch(CONFIG.proxyUrl, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        messages: [
          { role: 'system', content: STRATEGY_PROMPT },
          { role: 'user', content: content || 'Generate a sample Polymarket strategy for BTC price prediction' }
        ],
        free_tier: true
      })
    })
    const d = await r.json()
    if (!d.ok) throw new Error(d.error)

    let strategy
    try { strategy = JSON.parse(d.content) }
    catch(e) {
      const m = d.content.match(/\{[\s\S]*\}/)
      strategy = m ? JSON.parse(m[0]) : null
    }
    if (strategy) renderStrategyResult(strategy)
    else throw new Error('Could not parse strategy JSON')

  } catch(e) {
    document.getElementById('strategyResult').innerHTML =
      `<div class="card" style="color:#ef4444;font-size:.82rem">❌ ${e.message}</div>`
  }

  btn.innerHTML = '✨ Generate Strategy'
  btn.disabled = false
}

function renderStrategyResult(s) {
  const fields = [
    ['Entry', s.entry_condition], ['Exit', s.exit_condition],
    ['Stop Loss', s.stop_loss], ['Take Profit', s.take_profit],
    ['Max Position', s.max_position ? `$${s.max_position}` : null],
    ['Trailing Stop', s.trailing_stop ? `${(s.trailing_stop*100).toFixed(0)}%` : null],
  ].filter(([,v]) => v != null)

  document.getElementById('strategyResult').innerHTML = `
    <div class="card">
      <div style="font-weight:700;font-size:.95rem;margin-bottom:4px">${s.name || 'Strategy'}</div>
      <div style="color:#94a3b8;font-size:.78rem;margin-bottom:10px">${s.description || ''}</div>
      ${fields.map(([k,v]) => `
        <div class="pos-row"><span class="pos-label">${k}</span><span>${v}</span></div>
      `).join('')}
      <div class="btn-row" style="margin-top:12px">
        <button class="btn btn-primary" style="font-size:.8rem" onclick='deployStrategy(${JSON.stringify(JSON.stringify(s))})'>▶ Deploy to Mac</button>
        <button class="btn btn-ghost" style="font-size:.8rem" onclick="copyToClipboard()">📋 Copy</button>
      </div>
    </div>
  `
  window._lastStrategy = s
}

async function deployStrategy(sJson) {
  const tier = localStorage.getItem('selected_tier')
  if (!tier) {
    // 显示简单提示弹窗
    const choice = confirm(
      '部署策略需要付费：\n\n' +
      '• Mini: $9.9/策略（本地运行永久免费）\n' +
      '• Pro: $19/月（10个策略）\n' +
      '• Max: $19.9/年（无限策略）\n\n' +
      '点击确定前往官网选择方案'
    )
    if (choice) chrome.tabs.create({ url: 'https://iearn.bot/#pricing' })
    return
  }
  // 已有套餐，正常部署
  const s = JSON.parse(sJson)
  try {
    await apiCall('generate_strategy', { name: s.name, description: s.description, market: s.market || 'polymarket' })
    alert('✅ Strategy sent to Mac mini!')
  } catch(e) {
    alert('❌ Cannot reach Mac mini. Check Settings.')
  }
}

function copyToClipboard() {
  if (window._lastStrategy) {
    navigator.clipboard.writeText(JSON.stringify(window._lastStrategy, null, 2))
    alert('📋 Copied!')
  }
}

// ── Positions ─────────────────────────────────────────────────────────────
function renderPositions() {
  document.getElementById('content').innerHTML = `<div id="posList"><div class="empty">💼 Loading positions...</div></div>`
  loadPositions()
}

async function loadPositions() {
  try {
    const d = await apiCall('get_positions')
    const positions = d.positions || []
    document.getElementById('posList').innerHTML = positions.length
      ? positions.map(p => `
        <div class="pos-card">
          <div class="pos-header">
            <span>${p.market_id || p.id || 'Unknown'}</span>
            <span class="badge ${p.side === 'YES' ? 'badge-green' : 'badge-red'}">${p.side || 'YES'}</span>
          </div>
          <div class="pos-row"><span class="pos-label">Entry</span><span>$${Number(p.entry_price||0).toFixed(3)}</span></div>
          <div class="pos-row"><span class="pos-label">Current</span><span>$${Number(p.current_price||0).toFixed(3)}</span></div>
          <div class="pos-row"><span class="pos-label">Size</span><span>$${Number(p.size_usdc||0).toFixed(2)}</span></div>
          <div class="pos-row"><span class="pos-label">P&L</span>
            <span class="${Number(p.unrealized_pnl||0)>=0?'green':'red'}">
              ${Number(p.unrealized_pnl||0)>=0?'+':''}$${Number(p.unrealized_pnl||0).toFixed(2)}
            </span>
          </div>
        </div>`).join('')
      : '<div class="empty">📭 No open positions</div>'
  } catch(e) {
    document.getElementById('posList').innerHTML = '<div class="empty">⚡ Cannot reach Mac mini</div>'
  }
}

// ── Settings ──────────────────────────────────────────────────────────────
function renderSettings() {
  document.getElementById('content').innerHTML = `
    <div class="card">
      <label class="label">🖥️ Mac Mini Server URL</label>
      <input type="url" id="serverUrl" class="input" placeholder="http://192.168.1.xxx:7799" value="${CONFIG.serverUrl}" />
      <button class="btn btn-ghost" onclick="testConnection()">🔌 Test Connection</button>
      <div id="connStatus" style="font-size:.78rem;margin-top:6px;color:#64748b"></div>
    </div>
    <div class="card">
      <label class="label">💳 SkillPay User ID</label>
      <input type="text" id="skillpayId" class="input" placeholder="Telegram ID or wallet address"
        value="${localStorage.getItem('skillpay_id')||''}" />
      <div style="font-size:.72rem;color:#475569">For AI strategy generation billing.</div>
    </div>
    <button class="btn btn-primary" onclick="saveSettings()">💾 Save Settings</button>
    <div style="height:8px"></div>
    <button class="btn btn-danger" onclick="killSwitch()">🔴 Kill Switch — Stop All Trading</button>
    <div style="text-align:center;color:#334155;font-size:.7rem;margin-top:14px">iEarn.Bot v0.4.0 · MIT License</div>
  `
}

function saveSettings() {
  localStorage.setItem('server_url', document.getElementById('serverUrl').value.trim())
  localStorage.setItem('skillpay_id', document.getElementById('skillpayId').value.trim())
  const el = document.getElementById('connStatus')
  el.textContent = '✅ Saved'
  el.style.color = '#22c55e'
}

async function testConnection() {
  const url = document.getElementById('serverUrl').value.trim()
  const el = document.getElementById('connStatus')
  el.textContent = 'Testing...'
  el.style.color = '#94a3b8'
  try {
    const r = await fetch(`${url}/api/status`, { signal: AbortSignal.timeout(5000) })
    el.textContent = r.ok ? '✅ Connected' : '❌ Server error'
    el.style.color = r.ok ? '#22c55e' : '#ef4444'
  } catch(e) {
    el.textContent = '❌ Cannot reach server'
    el.style.color = '#ef4444'
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────
async function apiCall(cmd, args = {}) {
  const r = await fetch(`${CONFIG.serverUrl}/api/ipc`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cmd, args }),
    signal: AbortSignal.timeout(10000)
  })
  return r.json()
}

async function killSwitch() {
  if (!confirm('Stop all trading now?')) return
  try {
    await apiCall('kill_switch', { enable: true })
    alert('✅ Kill switch activated')
  } catch(e) {
    alert('❌ Cannot reach Mac mini')
  }
}

// ── Strategy Prompt ───────────────────────────────────────────────────────
const STRATEGY_PROMPT = `You are an expert trading strategy generator for prediction markets.
Given an article or idea, generate a complete JSON trading strategy. Return ONLY valid JSON, no markdown:
{
  "name": "Strategy name",
  "description": "One line description",
  "market": "polymarket",
  "entry_condition": "e.g. YES price < 0.40",
  "exit_condition": "e.g. YES price > 0.75 or stop_loss",
  "stop_loss": 0.25,
  "take_profit": 0.78,
  "max_position": 20,
  "trailing_stop": 0.12,
  "max_daily_loss": 15,
  "cooldown_period": 300,
  "kill_switch": false
}`

// ── Init ──────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  renderDashboard()
  setInterval(refreshDashboard, 30000)
})
