# Strategy Generation E2E Test Results

**Date:** 2026-03-07  
**Tester:** iEranBot subagent  
**Status:** ✅ ALL TESTS PASSING (after fixes)

---

## Bugs Found & Fixed

### Bug 1 — `generate-v2` CLI: missing `--text` argument
- **File:** `src/strategy_ai.py`
- **Issue:** The `generate-v2` argparse subcommand had `--url` and `description` but no `--text` flag. Running with `--text` caused `unrecognized arguments` error.
- **Fix:** Added `p_gen2.add_argument("--text", ...)` and wired it into the `generate-v2` handler to use text as content input.

### Bug 2 — `strategy_ai.py`: `requests` not imported at module level
- **File:** `src/strategy_ai.py`
- **Issue:** `_call_proxy()` called `requests.post(...)` but `requests` was only imported inside sub-functions. Caused `NameError: name 'requests' is not defined`.
- **Fix:** Added `import requests` at top of file alongside other standard imports.

### Bug 3 — `ipc_server.py`: print statements from `generate_strategy_v2` polluting stdout
- **File:** `src/ipc_server.py`
- **Issue:** `strategy_ai.generate_strategy_v2()` prints progress messages (e.g., `🤖 Generating V2 strategy`) directly to stdout. Since the IPC protocol uses stdout for JSON responses, these non-JSON lines corrupt the stream and break the Electron frontend parser.
- **Fix:** In `handle_generate_strategy()`, temporarily redirect `sys.stdout → sys.stderr` while calling `generate_strategy_v2()`, then restore stdout. All print output now goes to stderr (logs), stdout is clean JSON.

### Improvement — JSON parsing robustness in `generate_strategy_v2`
- **File:** `src/strategy_ai.py`
- **Improvement:** Enhanced JSON parsing to handle edge cases:
  - Strip multiline markdown code fences (```` ```json ... ``` ````)
  - If `json.loads` fails, try regex extraction of `{...}` block
  - Fall back to template strategy if AI returns non-JSON

---

## Test Results

### Test 1: Python CLI Direct Test ✅
```bash
python3 src/strategy_ai.py generate-v2 "BTC breakout prediction" \
  --text "Bitcoin is showing strong momentum above the 200-day moving average. \
  Polymarket has a market: Will BTC exceed 100k by end of March? Current odds YES at 0.45."
```
**Output:**
- ✅ JSON saved: `data/strategies/V4.json`
- ✅ YAML saved: `data/strategies/V4_params.yaml`

**Risk fields check:**
| Field | Present | Value |
|-------|---------|-------|
| stop_loss | ✅ | 0.3 |
| take_profit | ✅ | 0.8 |
| trailing_stop | ✅ | 0.1 |
| max_position | ✅ | 50 |
| max_daily_loss | ✅ | 25 |
| max_drawdown | ✅ | 0.3 |
| cooldown_period | ✅ | 300 |
| kill_switch | ✅ | false |

**Generated JSON:**
```json
{
  "name": "V4_BTC_100K_MAR",
  "description": "Strategy to capture BTC breakout above 200-day MA and capitalize on rising odds of BTC exceeding 100k by end of March",
  "market_adapter": "polymarket",
  "entry": { "trigger": "BTC price above 200-day moving average", "min_liquidity": 5000, "max_spread": 0.05, "categories": ["crypto"] },
  "position": { "side": "YES", "size_usdc": 10, "max_positions": 5, "max_order_size": 15, "max_position": 50 },
  "exit": { "take_profit": 0.8, "stop_loss": 0.3, "trailing_stop": 0.1, "resolve_redeem": true },
  "risk": { "max_daily_loss": 25, "max_drawdown": 0.3, "cooldown_period": 300, "kill_switch": false },
  "schedule": { "mode": "interval", "every": 15, "unit": "minutes" }
}
```

---

### Test 2: API Proxy Test (https://iearn.bot/api/chat) ✅
```bash
curl -s -X POST https://iearn.bot/api/chat -H "Content-Type: application/json" \
  -d '{"messages":[...],"free_tier":true}'
```
**Result:** `{"ok": true, "content": "...<JSON strategy>...", "model": "anthropic/claude-3-haiku", ...}`

- ✅ API responds with HTTP 200
- ✅ All required fields present: name, description, market, entry_condition, exit_condition, stop_loss, take_profit, max_position, trailing_stop, cooldown_period, max_daily_loss
- ✅ Usage/cost breakdown returned

---

### Test 3: IPC Server Test ✅

> **Note:** The original task test format used `"command"` and `"params"` keys, but the actual IPC protocol uses `"cmd"` and `"args"`. Corrected format used in test.

```json
{"id":"t1","cmd":"generate_strategy","args":{"text":"BTC exceed 100k March YES 0.45."}}
```

**Result (clean JSON stdout):**
```json
{
  "id": "t1",
  "ok": true,
  "data": {
    "name": "V4_BTC_100k_March",
    "market_adapter": "polymarket",
    "entry": {"trigger": "BTC price exceeds $100,000 by March", ...},
    "position": {"side": "YES", "size_usdc": 10, "max_positions": 5, "max_order_size": 15, "max_position": 50},
    "exit": {"take_profit": 0.8, "stop_loss": 0.3, "trailing_stop": 0.1, "resolve_redeem": true},
    "risk": {"max_daily_loss": 25, "max_drawdown": 0.3, "cooldown_period": 300, "kill_switch": false},
    "schedule": {"mode": "interval", "every": 15, "unit": "minutes"}
  }
}
```
- ✅ Stdout is clean JSON-only (no print pollution)
- ✅ Full strategy with all risk fields returned
- ✅ IPC protocol intact for Electron frontend

---

## Summary

| Test | Before Fix | After Fix |
|------|-----------|-----------|
| Test 1: CLI `--text` | ❌ `unrecognized arguments` | ✅ Generates JSON + params.yaml |
| Test 2: API proxy | ✅ Already working | ✅ Working |
| Test 3: IPC server | ⚠️ JSON mixed with print output | ✅ Clean JSON stdout |
| JSON parse robustness | ⚠️ Crashes on non-JSON response | ✅ Fallback to template |
| `requests` import | ❌ `NameError` | ✅ Top-level import |

All 3 tests pass. Strategy generation pipeline is fully operational.
