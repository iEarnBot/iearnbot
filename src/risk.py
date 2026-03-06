"""
risk.py — Stop-Loss & Take-Profit Manager
Runs every 5 minutes via launchd to check open positions.
"""
import logging
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
    log.info(f"[Risk] Checking {len(positions)} open position(s)")
    for pf in positions:
        import json
        pos = json.loads(pf.read_text())
        # TODO: check current market price vs stop_loss/take_profit
        log.info(f"[Risk] Position: {pos.get('market_id', 'unknown')} | side: {pos.get('side')} | entry: {pos.get('entry_price')}")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(BASE / "data" / "logs" / "bot.log"),
            logging.StreamHandler()
        ]
    )
    log.info("=== Risk Manager running ===")
    check_positions()
    log.info("=== Risk Manager complete ===")
