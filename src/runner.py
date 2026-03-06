"""
runner.py — Strategy Runner
Runs specified strategies: python3 src/runner.py v1 v2 v3
"""
import sys, os, logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
BASE = Path(__file__).parent.parent
log_dir = BASE / "data" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "bot.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("runner")

def run_strategy(name: str):
    log.info(f"Running strategy: {name.upper()}")
    try:
        if name == "v1":
            from strategy_v1 import run; run()
        elif name == "v2":
            from strategy_v2 import run; run()
        elif name == "v3":
            from strategy_v3 import run; run()
        else:
            # Custom strategy from data/strategies/
            import json
            sf = BASE / "data" / "strategies" / f"{name.upper()}.json"
            if sf.exists():
                strategy = json.loads(sf.read_text())
                log.info(f"Loaded custom strategy: {strategy.get('name')}")
                # TODO: execute custom strategy
            else:
                log.warning(f"Strategy file not found: {sf}")
    except Exception as e:
        log.error(f"Strategy {name} failed: {e}")

if __name__ == "__main__":
    strategies = sys.argv[1:] if len(sys.argv) > 1 else ["v1"]
    log.info(f"=== iEarn.Bot Runner starting: {strategies} ===")
    for s in strategies:
        run_strategy(s.lower())
    log.info("=== Runner complete ===")
