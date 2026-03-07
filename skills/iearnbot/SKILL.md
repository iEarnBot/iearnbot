---
name: iearnbot
description: >
  iEranBot AI trading strategy assistant. Use when user asks to generate trading
  strategies from articles or URLs, manage prediction market bots (Polymarket),
  add or test market adapters, run or stop or schedule strategies, check P&L or
  positions, configure risk controls (stop-loss, kill-switch, drawdown), or
  deploy iEranBot on macOS. Supports Polymarket and extensible multi-market framework.
---

# iEranBot Skill

iEranBot is a local AI-powered trading strategy bot. This skill provides workflows for operating and extending it.

## Architecture

```
electron/          # Desktop App (macOS dmg / Windows exe)
src/
  strategy_ai.py   # AI strategy generator (URL → strategy)
  scheduler.py     # APScheduler-based strategy runner
  risk.py          # Full risk engine (trailing stop, kill-switch)
  ipc_server.py    # Electron↔Python IPC bridge (JSON over stdio)
  key_store.py     # Secure API key storage (macOS Keychain / AES-256)
  adapters/        # Pluggable market adapters
    base.py        # MarketAdapter ABC
    generator.py   # AI-powered adapter generator from URL
    polymarket_adapter.py
    binance_adapter.py
    kalshi_adapter.py
data/
  strategies/      # Generated strategy JSON + params.yaml
  positions/       # Open positions (JSON per position)
  risk/            # kill_switch.flag, daily_loss.json, cooldown.json
  logs/bot.log
```

## Key Workflows

### Generate a Strategy from Article
```bash
python src/strategy_ai.py generate-v2 "BTC breakout" --url "https://x.com/..."
# → data/strategies/V4.json + V4_params.yaml
```
If URL fails, user pastes text directly. Output includes full risk params.

### Schedule & Run Strategy
```bash
python src/scheduler.py add v4 interval 15 minutes
python src/scheduler.py start
python src/scheduler.py list        # show all jobs + next run time
python src/scheduler.py run-now v4  # manual trigger
```

### Risk Controls
```bash
python src/risk.py kill             # enable kill-switch (halt all trading)
python src/risk.py resume           # disable kill-switch
python src/risk.py status           # show risk state
```
Per-position risk fields: `max_position`, `max_daily_loss`, `max_drawdown`, `trailing_stop`, `cooldown_period`, `max_order_size`, `kill_switch`.

### Add New Market
```bash
python src/adapters/generator.py generate https://kalshi.com
# → src/adapters/kalshi_adapter.py + kalshi_schema.json
python src/adapters/kalshi_adapter.py smoke  # connectivity test (read-only)
```

### Key Storage
```bash
python src/key_store.py set polymarket private_key "0x..."
python src/key_store.py get polymarket private_key
python src/key_store.py list
```
Uses macOS Keychain (primary) or AES-256-GCM encrypted file (fallback).

### IPC Server (for Electron)
```bash
python src/ipc_server.py
# Reads JSON commands from stdin, writes responses to stdout
# Supported: get_balances, get_positions, generate_strategy,
#   run_strategy, stop_strategy, kill_switch, get_logs,
#   add_market, list_markets, smoke_test, get/save_strategy_params,
#   list_strategies, scheduler_status, fetch_url
```

### Build dmg
```bash
cd electron && npm run build:dmg
# → dist/iEarn.Bot-0.4.0-arm64.dmg (89MB)
# → dist/iEarn.Bot-0.4.0.dmg (94MB, Intel)
```

## LLM Proxy
All AI calls route through `https://iearn.bot/api/chat` (Vercel serverless).
- No API key in client code
- SkillPay billing on server side
- User env: `SKILLPAY_USER_ID` only
- Max tier: set `OPENROUTER_API_KEY` to bypass proxy

## References
- See `references/risk_params.md` for full risk parameter documentation
- See `references/adapter_api.md` for market adapter interface spec
