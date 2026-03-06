# iEarn.Bot 🔥

> AI-Powered Prediction Market Bot — runs locally on your machine

**Your keys. Your funds. Your rules.**

[![MIT License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![Website](https://img.shields.io/badge/website-iearn.bot-f97316.svg)](https://iearn.bot)

---

## ✨ What is iEarn.Bot?

iEarn.Bot lets you automate trading on [Polymarket](https://polymarket.com) using AI-generated strategies. Describe a strategy in plain English — AI builds the rules and runs them 24/7 on your local machine.

**Free strategies** (V1/V2/V3) need no AI credits. **AI strategy generation** uses [SkillPay](https://skillpay.me) — pay ~0.01 USDT per call, no subscription.

---

## 🚀 Quick Install (macOS / Linux)

```bash
# 1. Clone
git clone https://github.com/iEarnBot/iearnbot ~/iearnbot

# 2. Install & configure
cd ~/iearnbot && bash setup.sh

# 3. Dashboard auto-opens at:
#    http://localhost:7799
```

**Requirements:** Python 3.11+, macOS or Linux

---

## ⚙️ Configuration (.env)

After install, your `.env` file is at `~/iearnbot/.env` (chmod 600):

| Variable | Description |
|----------|-------------|
| `POLYGON_PRIVATE_KEY` | Your Polygon wallet private key (never leaves your machine) |
| `SKILLPAY_API_KEY` | From [skillpay.me](https://skillpay.me) Dashboard → Integration Config |
| `SKILLPAY_USER_ID` | Your Telegram ID (number) or wallet address |
| `OPENROUTER_API_KEY` | Optional — for Max tier (unlimited AI calls) |
| `TRACK_WALLETS` | Optional — comma-separated addresses for V3 strategy |

---

## 🤖 Strategies

| Strategy | Description | Cost |
|----------|-------------|------|
| **V1** — BTC Momentum | Buys YES on BTC markets when bullish signal | Free |
| **V2** — Leaderboard Copy | Mirrors top Polymarket traders | Free |
| **V3** — Wallet Tracking | Copies specific wallet addresses | Free |
| **V4+** — AI Generated | Describe in plain English, Claude generates rules | ~0.01 USDT |

### Generate a custom AI strategy:
```bash
python3 src/strategy_ai.py generate "BTC breaks $100k by Q2, buy YES"
```

---

## 💳 SkillPay — Pay-Per-Use AI

1. Register at [skillpay.me](https://skillpay.me)
2. Top up with BNB Chain USDT
3. Add your API key to `.env`
4. Each AI strategy call auto-deducts ~0.01 USDT

No subscription. No signup required for free strategies.

---

## 📊 Dashboard

Access at **http://localhost:7799** after running setup.

Shows: P&L · Open positions · Strategy status · Recent logs

---

## 🗂️ Project Structure

```
iearnbot/
├── setup.sh          # One-command installer
├── requirements.txt  # Python dependencies
├── .env.example      # Config template
└── src/
    ├── skillpay.py       # SkillPay billing
    ├── strategy_ai.py    # AI strategy generator
    ├── strategy_v1.py    # BTC momentum
    ├── strategy_v2.py    # Leaderboard copy
    ├── strategy_v3.py    # Wallet tracking
    ├── runner.py         # Strategy runner
    ├── risk.py           # Stop-loss / take-profit
    └── dashboard.py      # Local web UI
```

---

## ⚠️ Disclaimer

This is experimental software. Prediction markets are speculative. Only use funds you can afford to lose entirely. DYOR. Not financial advice.

---

## 📄 License

MIT — © 2026 iEarn.Bot
