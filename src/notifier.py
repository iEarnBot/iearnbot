"""
notifier.py — Telegram Alert System
Sends alerts when: balance low, stop-loss triggered, strategy error, daily summary.

Configure via .env:
  ALERT_BOT_TOKEN=<Telegram bot token from @BotFather>
  ALERT_CHAT_ID=<your chat/user ID>
"""
import logging
import os

import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("notifier")

TELEGRAM_BOT_TOKEN: str = os.getenv("ALERT_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str   = os.getenv("ALERT_CHAT_ID", "")

_LEVEL_EMOJI = {
    "info":     "ℹ️",
    "warning":  "⚠️",
    "critical": "🚨",
}

_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_alert(message: str, level: str = "info") -> bool:
    """
    Send a Telegram alert message.

    Args:
        message: Text body of the alert.
        level:   Severity — "info", "warning", or "critical".

    Returns:
        True if the message was delivered, False otherwise.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("[notifier] ALERT_BOT_TOKEN or ALERT_CHAT_ID not set — skipping alert")
        return False

    emoji = _LEVEL_EMOJI.get(level.lower(), "ℹ️")
    text = f"{emoji} *iEarn.Bot* — `{level.upper()}`\n\n{message}"

    try:
        resp = requests.post(
            _API_URL.format(token=TELEGRAM_BOT_TOKEN),
            json={
                "chat_id":    TELEGRAM_CHAT_ID,
                "text":       text,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
        resp.raise_for_status()
        log.info(f"[notifier] Alert sent ({level}): {message[:80]}")
        return True
    except requests.RequestException as exc:
        log.error(f"[notifier] Failed to send alert: {exc}")
        return False


def alert_balance_low(balance: float, threshold: float = 0.1) -> bool:
    """
    Send a warning when SkillPay balance drops below *threshold* USDT.

    Args:
        balance:   Current USDT balance.
        threshold: Alert threshold (default 0.10 USDT).

    Returns:
        True if alert was sent, False otherwise.
    """
    if balance >= threshold:
        return False  # balance is fine, no alert needed
    msg = (
        f"Your SkillPay balance is running low!\n\n"
        f"💰 Current balance: *{balance:.4f} USDT*\n"
        f"📉 Threshold: {threshold:.4f} USDT\n\n"
        f"Top up at https://skillpay.me to keep AI strategies running."
    )
    return send_alert(msg, level="warning")


def alert_stop_loss(market: str, loss_pct: float) -> bool:
    """
    Alert when a stop-loss is triggered.

    Args:
        market:   Market identifier / question string.
        loss_pct: Loss percentage (e.g. 0.15 = 15 % loss).

    Returns:
        True if alert was sent.
    """
    msg = (
        f"Stop-loss triggered!\n\n"
        f"📊 Market: `{market}`\n"
        f"📉 Loss: *{loss_pct * 100:.1f}%*\n\n"
        f"Position has been flagged for exit. (Execution in v0.4)"
    )
    return send_alert(msg, level="critical")


def alert_take_profit(market: str, gain_pct: float) -> bool:
    """
    Alert when a take-profit target is hit.

    Args:
        market:   Market identifier / question string.
        gain_pct: Gain percentage (e.g. 0.25 = 25 % gain).

    Returns:
        True if alert was sent.
    """
    msg = (
        f"Take-profit target reached! 🎯\n\n"
        f"📊 Market: `{market}`\n"
        f"📈 Gain: *{gain_pct * 100:.1f}%*\n\n"
        f"Position has been flagged for exit. (Execution in v0.4)"
    )
    return send_alert(msg, level="info")


def alert_strategy_error(strategy_name: str, error: str) -> bool:
    """
    Alert when a strategy encounters an unhandled exception.

    Args:
        strategy_name: Human-readable strategy name (e.g. "V1 — BTC Momentum").
        error:         Short error description / exception text.

    Returns:
        True if alert was sent.
    """
    msg = (
        f"Strategy error detected!\n\n"
        f"🤖 Strategy: `{strategy_name}`\n"
        f"❌ Error: `{error[:300]}`\n\n"
        f"Check logs at ~/iearnbot/data/logs/bot.log"
    )
    return send_alert(msg, level="critical")


def alert_daily_summary(pnl: float, positions: int, strategies_run: int) -> bool:
    """
    Send a daily summary (intended to be called at 08:00 local time via cron/launchd).

    Args:
        pnl:            Total P&L in USDT for the period.
        positions:      Number of open positions.
        strategies_run: Number of strategy cycles executed.

    Returns:
        True if alert was sent.
    """
    direction = "📈" if pnl >= 0 else "📉"
    sign      = "+" if pnl >= 0 else ""
    msg = (
        f"Daily Summary 🗓\n\n"
        f"{direction} P&L: *{sign}{pnl:.4f} USDT*\n"
        f"📊 Open positions: {positions}\n"
        f"🤖 Strategy cycles run: {strategies_run}\n\n"
        f"Dashboard → http://localhost:7799"
    )
    return send_alert(msg, level="info")
