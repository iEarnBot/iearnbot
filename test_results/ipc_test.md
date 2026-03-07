# IPC Test Report
**Date**: 2026-03-07  
**Tester**: subagent test-electron-ipc

---

## Test 1: Python IPC Server — Direct Command Tests

| Command | Result | Data |
|---------|--------|------|
| `get_balances` | ✅ OK | `{"usdc": 0.0, "native": 0.0}` |
| `list_strategies` | ✅ OK | `{"strategies": [], "note": "No state file found"}` |
| `scheduler_status` | ✅ OK (after fix) | `{"jobs": []}` |
| `get_positions` | ✅ OK | `{"positions": []}` |
| `get_logs` | ✅ OK | Returns last 2 log lines |
| `list_markets` | ✅ OK | 3 markets (binance, kalshi, polymarket) |

**Issue found & fixed**: `scheduler_status` failed initially with `No module named 'apscheduler'`.  
**Fix**: Installed `apscheduler` via `pip3 install apscheduler`.

---

## Test 2: Electron main.js IPC Integration

### Python spawn
- ✅ `pythonPath` auto-detected via `which python3`
- ✅ `stdio: ['pipe', 'pipe', 'pipe']` configured correctly
- ✅ `cwd` set to workspace root

### Request-Response ID Matching — BUG FOUND & FIXED

**Problem**: Original code attached a new `data` listener per request via `pyProcess.stdout.on('data', handler)` and removed it after getting a response with matching `id`. This had two issues:
1. **Chunk-split vulnerability**: Node.js `data` events may deliver partial lines. If a JSON line is split across two `data` events, `JSON.parse()` would fail silently and the request would hang until timeout.
2. **Multiple listeners accumulation**: Each in-flight request added a listener; if the IPC server was slow, many listeners could accumulate.

**Fix applied to `electron/main.js`**:
- Added `_pyLineBuffer` string accumulator for partial lines
- Added `_pendingRequests` Map for centralized request tracking
- Single `data` listener in `startPythonIPC()` now routes responses to pending handlers by `msg.id`
- `py:send` handler now registers in `_pendingRequests` instead of adding per-request listeners
- Timeout handler cleans up `_pendingRequests` entry properly

### Auto-restart
**Problem**: If Python process crashed, pyProcess became `null` and all future `py:send` calls would fail with "Python IPC server not running".

**Fix**: Added auto-restart logic (3s delay) in `pyProcess.on('exit')`. Also added `app.isQuitting` flag to prevent restart loop on app quit. All pending requests are rejected immediately on process exit.

---

## Test 3: Renderer Page IPC Calls

| Page | IPC calls | Status |
|------|-----------|--------|
| `run.html` | `list_strategies`, `scheduler_status`, `run_strategy`, `stop_strategy`, `kill_switch` | ✅ Uses `ipc.pyCmd` correctly |
| `logs.html` | `get_logs`, `onPyEvent` (for live tail) | ✅ Uses `ipc.pyCmd` correctly |
| `markets.html` | `list_markets`, `smoke_test`, `add_market` | ✅ Uses `ipc.pyCmd` correctly |

All pages use `window.top?.ipcApi || window.ipcApi` with graceful fallback to localStorage — correct pattern for iframe context.

---

## Additional Fix: Balance Display in app.js

**Problem**: `index.html` has `<span id="balanceDisplay">—</span>` but `app.js` never called `get_balances` to populate it.

**Fix applied to `electron/renderer/app.js`**:
- Added `refreshBalance()` function that calls `ipc.pyCmd({ cmd: 'get_balances' })`
- Displays `X.XX USDC` or `X.XX USDC | Y.YYYY MATIC` depending on available data
- Called on startup and every 30 seconds

---

## Summary

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| 1 | `apscheduler` not installed → `scheduler_status` fails | Medium | ✅ Fixed (pip install) |
| 2 | Chunk-split JSON vulnerability in `py:send` listener | High | ✅ Fixed (line buffer) |
| 3 | Per-request data listeners leak when concurrent requests | Medium | ✅ Fixed (central Map) |
| 4 | No auto-restart if Python IPC crashes | Medium | ✅ Fixed |
| 5 | Balance display `balanceDisplay` never populated | Low | ✅ Fixed |

### Files Modified
- `electron/main.js` — IPC reliability (line buffer, central pending map, auto-restart)
- `electron/renderer/app.js` — Balance display
- `src/ipc_server.py` — No changes needed; protocol is correct
