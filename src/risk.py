"""
risk.py — Full Risk Engine v0.4
Runs every 5 minutes via launchd to check open positions.

v0.4 upgrades:
  • Full configurable risk parameters per position (with global defaults)
  • Global kill-switch via data/risk/kill_switch.flag
  • Daily loss tracking via data/risk/daily_loss.json
  • Trailing stop with peak_price tracking
  • REAL order execution for stop-loss / take-profit exit
  • Cooldown period enforcement after a stop trigger
  • data/risk/closed_positions.jsonl audit trail

CLI:
  python src/risk.py          → run risk checks (normal mode)
  python src/risk.py kill     → create kill-switch flag (stop all trading)
  python src/risk.py resume   → remove kill-switch flag (resume trading)
  python src/risk.py status   → show risk state summary
"""

import json
import logging
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("risk")
BASE = Path(__file__).parent.parent

# ── Path constants ──────────────────────────────────────────────────────────
RISK_DIR           = BASE / "data" / "risk"
KILL_SWITCH_FLAG   = RISK_DIR / "kill_switch.flag"
DAILY_LOSS_FILE    = RISK_DIR / "daily_loss.json"
CLOSED_POSITIONS   = RISK_DIR / "closed_positions.jsonl"
COOLDOWN_FILE      = RISK_DIR / "cooldown.json"   # {position_id: last_stop_ts}
POSITIONS_DIR      = BASE / "data" / "positions"
LOG_DIR            = BASE / "data" / "logs"


# ── Helpers: kill-switch ────────────────────────────────────────────────────

def is_kill_switch_active() -> bool:
    """Return True if the global kill-switch is engaged."""
    if not KILL_SWITCH_FLAG.exists():
        return False
    content = KILL_SWITCH_FLAG.read_text().strip().lower()
    return content in ("1", "true", "yes", "on")


def set_kill_switch(active: bool) -> None:
    RISK_DIR.mkdir(parents=True, exist_ok=True)
    if active:
        KILL_SWITCH_FLAG.write_text("1")
        log.warning("[KillSwitch] ENGAGED — all trading suspended")
    else:
        if KILL_SWITCH_FLAG.exists():
            KILL_SWITCH_FLAG.unlink()
        log.info("[KillSwitch] DISENGAGED — trading resumed")


# ── Helpers: daily loss ─────────────────────────────────────────────────────

def _today() -> str:
    return date.today().isoformat()


def get_daily_loss() -> float:
    """Return today's cumulative realised loss in USDC (positive = loss)."""
    if not DAILY_LOSS_FILE.exists():
        return 0.0
    try:
        data = json.loads(DAILY_LOSS_FILE.read_text())
        if data.get("date") == _today():
            return float(data.get("loss_usdc", 0.0))
    except Exception:
        pass
    return 0.0


def add_daily_loss(amount_usdc: float) -> float:
    """
    Add *amount_usdc* (positive value = loss realised today).
    Returns new cumulative daily loss.
    """
    RISK_DIR.mkdir(parents=True, exist_ok=True)
    current = get_daily_loss()
    new_total = current + amount_usdc
    DAILY_LOSS_FILE.write_text(json.dumps({"date": _today(), "loss_usdc": round(new_total, 6)}))
    return new_total


def is_daily_loss_breached(max_daily_loss: float) -> bool:
    return get_daily_loss() >= max_daily_loss


# ── Helpers: cooldown ───────────────────────────────────────────────────────

def _load_cooldowns() -> dict:
    if not COOLDOWN_FILE.exists():
        return {}
    try:
        return json.loads(COOLDOWN_FILE.read_text())
    except Exception:
        return {}


def _save_cooldowns(cd: dict) -> None:
    RISK_DIR.mkdir(parents=True, exist_ok=True)
    COOLDOWN_FILE.write_text(json.dumps(cd))


def is_in_cooldown(position_id: str, cooldown_period: int) -> bool:
    """Return True if position is still within its post-stop cooldown window."""
    cd = _load_cooldowns()
    last_stop_ts = cd.get(position_id)
    if last_stop_ts is None:
        return False
    elapsed = time.time() - last_stop_ts
    return elapsed < cooldown_period


def set_cooldown(position_id: str) -> None:
    cd = _load_cooldowns()
    cd[position_id] = time.time()
    _save_cooldowns(cd)


# ── Helpers: closed positions audit trail ───────────────────────────────────

def record_closed_position(pos: dict, reason: str, exit_price: float, pnl_usdc: float) -> None:
    RISK_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "closed_at":   datetime.now(timezone.utc).isoformat(),
        "reason":      reason,
        "exit_price":  exit_price,
        "pnl_usdc":    round(pnl_usdc, 6),
        **{k: pos.get(k) for k in (
            "condition_id", "market", "side", "entry_price", "size",
            "stop_loss", "take_profit", "trailing_stop", "peak_price"
        )},
    }
    with open(CLOSED_POSITIONS, "a") as f:
        f.write(json.dumps(record) + "\n")
    log.info(f"[Risk] Closed position recorded: {record.get('market', '?')} | reason={reason} | pnl={pnl_usdc:+.2f}")


# ── Helpers: position risk config ───────────────────────────────────────────

def get_risk_config(pos: dict) -> dict:
    """
    Merge global DEFAULT_RISK with per-position overrides.
    Fields present in the position JSON always win.
    Backward-compatible: positions without risk fields use global defaults.
    """
    try:
        from risk_config import DEFAULT_RISK
    except ImportError:
        DEFAULT_RISK = {
            "max_position":  50,
            "max_daily_loss": 30,
            "max_drawdown":  0.35,
            "max_order_size": 20,
            "trailing_stop": 0.12,
            "cooldown_period": 300,
        }
    cfg = dict(DEFAULT_RISK)
    for key in DEFAULT_RISK:
        if key in pos:
            cfg[key] = pos[key]
    # stop_loss / take_profit are position-specific, not in DEFAULT_RISK
    for key in ("stop_loss", "take_profit", "kill_switch"):
        if key in pos:
            cfg[key] = pos[key]
    return cfg


# ── Close position: real execution ─────────────────────────────────────────

def execute_close(pos: dict, pf: Path, reason: str, exit_price: float,
                  polymarket_mod) -> None:
    """
    Execute a real close order via polymarket, then:
      • delete the position file
      • write to closed_positions.jsonl
      • accumulate daily loss if applicable
    """
    condition_id = pos.get("condition_id") or pos.get("market_id", "")
    side         = pos.get("side", "YES").upper()
    size         = float(pos.get("size", 0))
    entry_price  = float(pos.get("entry_price", 0))
    market_label = pos.get("market", condition_id[:12] if condition_id else pf.stem)

    # P&L estimate: positive = profit, negative = loss
    if side == "YES":
        pnl_usdc = (exit_price - entry_price) * size
    else:
        pnl_usdc = (entry_price - exit_price) * size

    log.warning(
        f"[Risk] CLOSING {market_label} | reason={reason} | "
        f"side={side} | size={size} | entry={entry_price:.4f} | exit={exit_price:.4f} | "
        f"pnl={pnl_usdc:+.2f} USDC"
    )

    # ── Place close order via polymarket ──────────────────────────────
    close_side = "NO" if side == "YES" else "YES"
    try:
        if hasattr(polymarket_mod, "place_order"):
            result = polymarket_mod.place_order(
                condition_id=condition_id,
                side=close_side,
                size=size,
                price=exit_price,
                order_type="market",
            )
            log.info(f"[Risk] Close order result: {result}")
        else:
            log.warning("[Risk] polymarket.place_order not available — position file will still be cleaned up")
    except Exception as exc:
        log.error(f"[Risk] Close order failed for {market_label}: {exc}")
        # Continue cleanup even if order fails (to avoid stuck positions)

    # ── Accumulate daily loss ─────────────────────────────────────────
    if pnl_usdc < 0:
        new_daily_loss = add_daily_loss(abs(pnl_usdc))
        log.info(f"[Risk] Daily loss updated: {new_daily_loss:.2f} USDC cumulative")

    # ── Record to audit trail ─────────────────────────────────────────
    record_closed_position(pos, reason, exit_price, pnl_usdc)

    # ── Remove position file ──────────────────────────────────────────
    try:
        pf.unlink()
        log.info(f"[Risk] Position file removed: {pf.name}")
    except Exception as exc:
        log.error(f"[Risk] Could not remove {pf.name}: {exc}")

    # ── Notify ────────────────────────────────────────────────────────
    try:
        from notifier import alert_stop_loss, alert_take_profit
        if reason == "stop_loss":
            loss_pct = abs(pnl_usdc) / max(entry_price * size, 1e-9)
            alert_stop_loss(market_label, loss_pct)
        elif reason == "take_profit":
            gain_pct = pnl_usdc / max(entry_price * size, 1e-9)
            alert_take_profit(market_label, gain_pct)
    except Exception:
        pass


# ── Core risk check ────────────────────────────────────────────────────────

def check_positions() -> None:
    """Main risk loop: iterate all open positions and enforce risk rules."""

    # 1. Global kill-switch check
    if is_kill_switch_active():
        log.warning("[Risk] KILL SWITCH IS ACTIVE — skipping all checks (trading suspended)")
        # Close every open position immediately
        _close_all_positions_kill_switch()
        return

    if not POSITIONS_DIR.exists():
        log.info("[Risk] No positions directory yet")
        return

    positions = list(POSITIONS_DIR.glob("*.json"))
    if not positions:
        log.info("[Risk] No open positions to check")
        return

    log.info(f"[Risk] Checking {len(positions)} open position(s)")

    # Lazy imports
    sys.path.insert(0, str(BASE / "src"))
    try:
        import polymarket
    except ImportError as exc:
        log.error(f"[Risk] Cannot import polymarket: {exc}")
        return

    for pf in positions:
        try:
            pos = json.loads(pf.read_text())
        except Exception as exc:
            log.error(f"[Risk] Cannot parse {pf.name}: {exc}")
            continue

        _check_single_position(pos, pf, polymarket)


def _close_all_positions_kill_switch() -> None:
    """Close every open position when kill-switch is active."""
    if not POSITIONS_DIR.exists():
        return

    sys.path.insert(0, str(BASE / "src"))
    try:
        import polymarket
    except ImportError as exc:
        log.error(f"[Risk] Cannot import polymarket: {exc}")
        polymarket = None  # type: ignore

    for pf in POSITIONS_DIR.glob("*.json"):
        try:
            pos = json.loads(pf.read_text())
        except Exception:
            continue

        condition_id = pos.get("condition_id") or pos.get("market_id", "")
        current_price = 0.0

        if polymarket and condition_id:
            price_data = polymarket.get_market_price(condition_id)
            side = pos.get("side", "YES").upper()
            current_price = (
                price_data.get("yes_price") if side == "YES"
                else price_data.get("no_price")
            ) or 0.0

        execute_close(pos, pf, "kill_switch", current_price, polymarket)


def _check_single_position(pos: dict, pf: Path, polymarket_mod) -> None:
    """Evaluate all risk rules for one position."""
    cfg            = get_risk_config(pos)
    condition_id   = pos.get("condition_id") or pos.get("market_id", "")
    market_label   = pos.get("market", condition_id[:12] if condition_id else pf.stem)
    side           = pos.get("side", "YES").upper()
    entry_price    = float(pos.get("entry_price", 0))
    size           = float(pos.get("size", 0))
    position_id    = pf.stem

    # Per-position kill-switch
    if cfg.get("kill_switch"):
        log.warning(f"[Risk] {market_label}: per-position kill_switch=true — closing immediately")
        price_data = polymarket_mod.get_market_price(condition_id) if condition_id else {}
        cur = (price_data.get("yes_price") if side == "YES" else price_data.get("no_price")) or 0.0
        execute_close(pos, pf, "kill_switch", cur, polymarket_mod)
        return

    # Daily loss gate: if today's loss already exceeds the limit, skip new closes
    # (We still check but won't execute orders — trading is suspended for today)
    max_daily_loss = float(cfg.get("max_daily_loss", 30))
    if is_daily_loss_breached(max_daily_loss):
        log.warning(
            f"[Risk] {market_label}: daily loss limit reached "
            f"({get_daily_loss():.2f} >= {max_daily_loss:.2f} USDC) — "
            f"order execution suspended for today"
        )
        # Still fetch price to update position file, but do NOT execute orders
        _update_price_only(pos, pf, condition_id, side, polymarket_mod)
        return

    # Cooldown gate
    cooldown_period = int(cfg.get("cooldown_period", 300))
    if is_in_cooldown(position_id, cooldown_period):
        remaining = cooldown_period - (time.time() - _load_cooldowns().get(position_id, 0))
        log.info(f"[Risk] {market_label}: in cooldown ({remaining:.0f}s remaining) — skipping")
        return

    # Fetch live price
    if not condition_id:
        log.warning(f"[Risk] {pf.name}: no condition_id — skipping price check")
        return

    price_data = polymarket_mod.get_market_price(condition_id)
    if not price_data:
        log.warning(f"[Risk] Could not fetch price for {condition_id[:12]}…")
        return

    current_price = (
        price_data.get("yes_price") if side == "YES"
        else price_data.get("no_price")
    )
    if current_price is None:
        log.warning(f"[Risk] No price for side={side} on {condition_id[:12]}…")
        return

    log.info(
        f"[Risk] {market_label} | side={side} | entry={entry_price:.4f} "
        f"| current={current_price:.4f} | size={size}"
    )

    # ── Update peak_price (trailing stop support) ─────────────────────
    peak_price = float(pos.get("peak_price") or entry_price or current_price)
    if current_price > peak_price:
        peak_price = current_price
        pos["peak_price"] = peak_price

    # ── Update current_price in position file ─────────────────────────
    pos["current_price"] = current_price
    pos["peak_price"]    = peak_price
    try:
        pf.write_text(json.dumps(pos, indent=2))
    except Exception as exc:
        log.warning(f"[Risk] Could not update {pf.name}: {exc}")

    # ── Max position size check ───────────────────────────────────────
    max_position = float(cfg.get("max_position", 50))
    position_value = current_price * size
    if position_value > max_position:
        log.warning(
            f"[Risk] {market_label}: position value {position_value:.2f} USDC "
            f"exceeds max_position={max_position:.2f} — alerting (no auto-close for oversize)"
        )
        # Oversize alert only; not an automatic close trigger

    # ── Max drawdown check ────────────────────────────────────────────
    max_drawdown = float(cfg.get("max_drawdown", 0.35))
    if entry_price > 0:
        drawdown = (entry_price - current_price) / entry_price if side == "YES" \
                   else (current_price - entry_price) / entry_price
        if drawdown >= max_drawdown:
            log.warning(
                f"[Risk] {market_label}: drawdown {drawdown*100:.1f}% >= max_drawdown "
                f"{max_drawdown*100:.1f}% — CLOSING (max_drawdown)"
            )
            execute_close(pos, pf, "max_drawdown", current_price, polymarket_mod)
            set_cooldown(position_id)
            return

    # ── Trailing stop check ────────────────────────────────────────────
    trailing_stop = float(cfg.get("trailing_stop", 0.12))
    trail_threshold = peak_price * (1.0 - trailing_stop)
    if current_price < trail_threshold:
        log.warning(
            f"[Risk] {market_label}: trailing stop triggered | "
            f"price={current_price:.4f} < peak={peak_price:.4f} * (1 - {trailing_stop}) "
            f"= {trail_threshold:.4f} — CLOSING (trailing_stop)"
        )
        execute_close(pos, pf, "trailing_stop", current_price, polymarket_mod)
        set_cooldown(position_id)
        return

    # ── Hard stop-loss check ──────────────────────────────────────────
    stop_loss = cfg.get("stop_loss")
    if stop_loss is not None:
        stop_loss = float(stop_loss)
        if current_price <= stop_loss:
            loss_pct = abs(current_price - entry_price) / max(entry_price, 1e-9)
            log.warning(
                f"[Risk] {market_label}: STOP LOSS triggered | "
                f"price={current_price:.4f} <= stop={stop_loss:.4f} | "
                f"loss={loss_pct*100:.1f}% — CLOSING (stop_loss)"
            )
            execute_close(pos, pf, "stop_loss", current_price, polymarket_mod)
            set_cooldown(position_id)
            return

    # ── Take-profit check ─────────────────────────────────────────────
    take_profit = cfg.get("take_profit")
    if take_profit is not None:
        take_profit = float(take_profit)
        if current_price >= take_profit:
            gain_pct = abs(current_price - entry_price) / max(entry_price, 1e-9)
            log.info(
                f"[Risk] {market_label}: TAKE PROFIT triggered | "
                f"price={current_price:.4f} >= tp={take_profit:.4f} | "
                f"gain={gain_pct*100:.1f}% — CLOSING (take_profit)"
            )
            execute_close(pos, pf, "take_profit", current_price, polymarket_mod)
            return


def _update_price_only(pos: dict, pf: Path, condition_id: str,
                       side: str, polymarket_mod) -> None:
    """Fetch and persist current price without executing any orders."""
    if not condition_id:
        return
    price_data = polymarket_mod.get_market_price(condition_id)
    if not price_data:
        return
    current_price = (
        price_data.get("yes_price") if side == "YES"
        else price_data.get("no_price")
    )
    if current_price is not None:
        peak_price = float(pos.get("peak_price") or pos.get("entry_price") or current_price)
        pos["current_price"] = current_price
        pos["peak_price"]    = max(peak_price, current_price)
        try:
            pf.write_text(json.dumps(pos, indent=2))
        except Exception:
            pass


# ── RiskEngine class (OO wrapper for unit-testing and programmatic use) ────

class RiskEngine:
    """
    Object-oriented wrapper around the risk module's functional helpers.
    Suitable for unit tests and direct programmatic use.

    Uses the same RISK_DIR / DAILY_LOSS_FILE / KILL_SWITCH_FLAG paths as the
    module-level functions so state is shared.
    """

    def __init__(self) -> None:
        # Ensure data/risk/ directory always exists on instantiation
        RISK_DIR.mkdir(parents=True, exist_ok=True)
        # In-memory peak price cache: {position_id: float}
        self._peaks: dict = {}

    # ── Kill-switch ──────────────────────────────────────────────────────

    def kill(self) -> None:
        set_kill_switch(True)

    def resume(self) -> None:
        set_kill_switch(False)

    def is_kill_switch_active(self) -> bool:
        return is_kill_switch_active()

    # ── Daily loss ───────────────────────────────────────────────────────

    def record_loss(self, amount_usdc: float) -> float:
        """Record a realised loss.  Returns new cumulative daily loss."""
        return add_daily_loss(amount_usdc)

    def get_daily_loss(self) -> float:
        return get_daily_loss()

    def is_trading_blocked(self, max_daily_loss: float = 30.0) -> bool:
        """Return True when cumulative daily loss >= max_daily_loss."""
        return is_daily_loss_breached(max_daily_loss)

    # ── Trailing stop ────────────────────────────────────────────────────

    def check_trailing_stop(self, pos: dict, trailing_pct: float = 0.12) -> bool:
        """
        Return True if the trailing stop should trigger for *pos*.

        Logic:
          • peak_price = max(pos.get("peak_price"), current_price)
            (also updated in self._peaks for stateful tracking)
          • trigger if current_price < peak_price * (1 - trailing_pct)

        The position dict is NOT mutated here; call update_peak() separately
        if you need to persist the new peak.
        """
        pos_id        = pos.get("id", id(pos))
        current_price = float(pos.get("current_price", pos.get("entry_price", 0)))
        stored_peak   = float(pos.get("peak_price") or pos.get("entry_price") or current_price)

        # Merge with in-memory cache
        mem_peak = self._peaks.get(pos_id, stored_peak)
        peak = max(stored_peak, mem_peak, current_price)

        # Update in-memory peak
        self._peaks[pos_id] = peak

        threshold = peak * (1.0 - trailing_pct)
        return current_price < threshold

    def update_peak(self, pos: dict) -> float:
        """Update and return the peak price for a position (call after each tick)."""
        pos_id        = pos.get("id", id(pos))
        current_price = float(pos.get("current_price", pos.get("entry_price", 0)))
        stored_peak   = float(pos.get("peak_price") or pos.get("entry_price") or current_price)
        mem_peak      = self._peaks.get(pos_id, stored_peak)
        peak          = max(stored_peak, mem_peak, current_price)
        self._peaks[pos_id] = peak
        return peak

    # ── Cooldown ─────────────────────────────────────────────────────────

    def set_cooldown(self, position_id: str) -> None:
        set_cooldown(position_id)

    def is_in_cooldown(self, position_id: str, cooldown_period: int = 300) -> bool:
        return is_in_cooldown(position_id, cooldown_period)

    # ── Full position check ──────────────────────────────────────────────

    def check_positions(self) -> None:
        check_positions()


# ── Status summary ─────────────────────────────────────────────────────────

def print_status() -> None:
    ks    = is_kill_switch_active()
    daily = get_daily_loss()
    positions = list(POSITIONS_DIR.glob("*.json")) if POSITIONS_DIR.exists() else []
    print(f"Kill-switch  : {'ACTIVE ⛔' if ks else 'off ✅'}")
    print(f"Daily loss   : {daily:.2f} USDC")
    print(f"Open positions: {len(positions)}")
    if CLOSED_POSITIONS.exists():
        closed = CLOSED_POSITIONS.read_text().strip().splitlines()
        print(f"Closed today : {len(closed)} record(s) in {CLOSED_POSITIONS.name}")


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    RISK_DIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "bot.log"),
            logging.StreamHandler(),
        ],
    )

    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd == "kill":
        set_kill_switch(True)
        print("Kill-switch ENGAGED. Run `python src/risk.py resume` to resume trading.")
        sys.exit(0)
    elif cmd == "resume":
        set_kill_switch(False)
        print("Kill-switch DISENGAGED. Trading resumed.")
        sys.exit(0)
    elif cmd == "status":
        print_status()
        sys.exit(0)
    else:
        log.info("=== Risk Manager v0.4 running ===")
        check_positions()
        log.info("=== Risk Manager complete ===")
