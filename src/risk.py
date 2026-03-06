"""
risk.py — Stop-Loss & Take-Profit Manager
Runs every 5 minutes via launchd to check open positions.

v0.3: reads real positions, fetches live prices, triggers alerts via notifier.
      Actual order execution is deferred to v0.4.
"""
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("risk")
BASE = Path(__file__).parent.parent


def check_positions():
    pos_dir = BASE / "data" / "positions"
    if not pos_dir.exists():
        log.info("[Risk] No positions directory yet")
        return

    positions = list(pos_dir.glob("*.json"))
    if not positions:
        log.info("[Risk] No open positions to check")
        return

    log.info(f"[Risk] Checking {len(positions)} open position(s)")

    # Lazy imports to avoid circular deps if run standalone
    sys.path.insert(0, str(BASE / "src"))
    try:
        import polymarket
    except ImportError as exc:
        log.error(f"[Risk] Cannot import polymarket: {exc}")
        return

    try:
        from notifier import alert_stop_loss, alert_take_profit
    except ImportError:
        # Graceful fallback if notifier is not yet available
        def alert_stop_loss(market, loss_pct):
            log.warning(f"[Risk] (no notifier) stop-loss alert for {market} ({loss_pct*100:.1f}%)")
        def alert_take_profit(market, gain_pct):
            log.info(f"[Risk] (no notifier) take-profit alert for {market} ({gain_pct*100:.1f}%)")

    for pf in positions:
        try:
            pos = json.loads(pf.read_text())
        except Exception as exc:
            log.error(f"[Risk] Cannot parse {pf.name}: {exc}")
            continue

        condition_id = pos.get("condition_id") or pos.get("market_id", "")
        market_label = pos.get("market", condition_id or pf.stem)
        side         = pos.get("side", "YES").upper()
        entry_price  = float(pos.get("entry_price", 0))
        stop_loss    = pos.get("stop_loss")    # e.g. 0.70 (exit if price <= this)
        take_profit  = pos.get("take_profit")  # e.g. 0.90 (exit if price >= this)
        size         = float(pos.get("size", 0))

        log.info(
            f"[Risk] {market_label} | side={side} | entry={entry_price:.4f} "
            f"| stop={stop_loss} | tp={take_profit} | size={size}"
        )

        if not condition_id:
            log.warning(f"[Risk] {pf.name}: no condition_id — skipping price check")
            continue

        # Fetch live price
        price_data = polymarket.get_market_price(condition_id)
        if not price_data:
            log.warning(f"[Risk] Could not fetch price for {condition_id[:12]}…")
            continue

        current_price = (
            price_data.get("yes_price") if side == "YES"
            else price_data.get("no_price")
        )
        if current_price is None:
            log.warning(f"[Risk] No price for side={side} on {condition_id[:12]}…")
            continue

        log.info(f"[Risk] {market_label}: current_price={current_price:.4f}")

        # Update position file with latest price (for dashboard P&L)
        pos["current_price"] = current_price
        try:
            pf.write_text(json.dumps(pos, indent=2))
        except Exception as exc:
            log.warning(f"[Risk] Could not update {pf.name}: {exc}")

        # ── Stop-Loss check ───────────────────────────────────────────
        if stop_loss is not None:
            stop_loss = float(stop_loss)
            if current_price <= stop_loss:
                loss_pct = abs(current_price - entry_price) / max(entry_price, 1e-9)
                log.warning(
                    f"[STOP LOSS TRIGGERED] {market_label} | "
                    f"price={current_price:.4f} <= stop={stop_loss:.4f} | "
                    f"loss={loss_pct*100:.1f}% | size={size} | "
                    f"[ORDER EXECUTION DEFERRED TO v0.4]"
                )
                alert_stop_loss(market_label, loss_pct)
                # TODO v0.4: place market sell order to exit position

        # ── Take-Profit check ─────────────────────────────────────────
        if take_profit is not None:
            take_profit = float(take_profit)
            if current_price >= take_profit:
                gain_pct = abs(current_price - entry_price) / max(entry_price, 1e-9)
                log.info(
                    f"[TAKE PROFIT TRIGGERED] {market_label} | "
                    f"price={current_price:.4f} >= tp={take_profit:.4f} | "
                    f"gain={gain_pct*100:.1f}% | size={size} | "
                    f"[ORDER EXECUTION DEFERRED TO v0.4]"
                )
                alert_take_profit(market_label, gain_pct)
                # TODO v0.4: place market sell order to lock in profit


if __name__ == "__main__":
    log_dir = BASE / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "bot.log"),
            logging.StreamHandler(),
        ],
    )
    log.info("=== Risk Manager v0.3 running ===")
    check_positions()
    log.info("=== Risk Manager complete ===")
