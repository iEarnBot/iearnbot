"""
ipc_server.py — Python IPC Bridge for Electron
读取 stdin JSON 命令，执行，写入 stdout JSON 响应。
日志写入 stderr（不污染 stdout 协议流）。

Protocol:
  stdin  → {"id": "req-1", "cmd": "get_balances", "args": {}}
  stdout → {"id": "req-1", "ok": true, "data": {...}}
         | {"id": "req-1", "ok": false, "error": "..."}
  stdout (push) → {"event": "log", "level": "INFO", "msg": "...", "ts": "..."}
"""

import sys
import json
import logging
import threading
import time
import glob
import importlib.util
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent

log = logging.getLogger("ipc")
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [IPC] %(message)s",
)

# ── stdout lock (shared between main loop and log-tail thread) ─────────────
_stdout_lock = threading.Lock()


def _emit(obj: dict):
    """Write a JSON object to stdout, thread-safe."""
    with _stdout_lock:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def _reply(req_id: str, data=None, error: str = None):
    if error is not None:
        _emit({"id": req_id, "ok": False, "error": error})
    else:
        _emit({"id": req_id, "ok": True, "data": data if data is not None else {}})


# ── lazy-loaded singletons ─────────────────────────────────────────────────
_scheduler_instance = None
_scheduler_lock = threading.Lock()


def _get_scheduler():
    global _scheduler_instance
    if _scheduler_instance is None:
        with _scheduler_lock:
            if _scheduler_instance is None:
                from scheduler import StrategyScheduler  # noqa: F401
                _scheduler_instance = StrategyScheduler()
    return _scheduler_instance


# ═══════════════════════════════════════════════════════════════════════════
# Handlers
# ═══════════════════════════════════════════════════════════════════════════

def handle_get_balances(args: dict) -> dict:
    """调用 polymarket_adapter.get_balances()"""
    sys.path.insert(0, str(BASE / "src"))
    from adapters.polymarket_adapter import PolymarketAdapter
    adapter = PolymarketAdapter()
    return adapter.get_balances()


def handle_get_positions(args: dict) -> dict:
    """读取 data/positions/*.json"""
    positions_dir = BASE / "data" / "positions"
    positions = []
    for fp in sorted(positions_dir.glob("*.json")):
        try:
            positions.append(json.loads(fp.read_text()))
        except Exception as e:
            log.warning(f"Failed to read {fp}: {e}")
    return {"positions": positions}


def handle_generate_strategy(args: dict) -> dict:
    """调用 strategy_ai.generate_strategy_v2(url+text)"""
    sys.path.insert(0, str(BASE / "src"))
    from strategy_ai import generate_strategy_v2, fetch_content
    url = args.get("url", "")
    text = args.get("text", "")
    # fetch content from URL if provided
    content = ""
    if url:
        try:
            content = fetch_content(url)
        except Exception as e:
            log.warning(f"fetch_content failed for {url}: {e}")
    if text:
        content = (content + "\n" + text).strip() if content else text
    strategy = generate_strategy_v2(content=content, description=text)
    return strategy


def handle_run_strategy(args: dict) -> dict:
    """调用 scheduler.add_strategy() + start()"""
    strategy_id = args.get("strategy_id", "v1")
    schedule = args.get("schedule", {"mode": "manual"})
    sched = _get_scheduler()

    # Build a dummy runner (real runner would import the actual strategy module)
    def _make_runner(sid):
        def runner():
            log.info(f"[RUN] strategy {sid} triggered")
        return runner

    sched.add_strategy(strategy_id, _make_runner(strategy_id), schedule)
    if not sched._scheduler.running:
        sched.start()
    return {"strategy_id": strategy_id, "status": "running", "schedule": schedule}


def handle_stop_strategy(args: dict) -> dict:
    """调用 scheduler.pause_strategy()"""
    strategy_id = args.get("strategy_id")
    if not strategy_id:
        raise ValueError("strategy_id is required")
    sched = _get_scheduler()
    sched.pause_strategy(strategy_id)
    return {"strategy_id": strategy_id, "status": "paused"}


def handle_kill_switch(args: dict) -> dict:
    """写/删 data/risk/kill_switch.flag"""
    enable = args.get("enable", True)
    flag_path = BASE / "data" / "risk" / "kill_switch.flag"
    flag_path.parent.mkdir(parents=True, exist_ok=True)
    if enable:
        flag_path.write_text(datetime.utcnow().isoformat())
        return {"kill_switch": True, "msg": "Kill switch ENABLED — all trading halted"}
    else:
        if flag_path.exists():
            flag_path.unlink()
        return {"kill_switch": False, "msg": "Kill switch DISABLED — trading resumed"}


def handle_get_logs(args: dict) -> dict:
    """读取 data/logs/bot.log 最后 N 行，按 level 过滤"""
    n_lines = int(args.get("lines", 100))
    level_filter = args.get("level", "all").upper()
    log_path = BASE / "data" / "logs" / "bot.log"
    if not log_path.exists():
        return {"lines": [], "note": "Log file not found"}

    with log_path.open("r", errors="replace") as f:
        all_lines = f.readlines()

    tail = all_lines[-n_lines:]
    if level_filter != "ALL":
        tail = [l for l in tail if level_filter in l.upper()]

    return {"lines": [l.rstrip("\n") for l in tail]}


def handle_add_market(args: dict) -> dict:
    """调用 AI 生成适配器骨架，保存到 src/adapters/<name>_adapter.py"""
    url = args.get("url", "")
    if not url:
        raise ValueError("url is required")

    # Derive market name from URL
    from urllib.parse import urlparse
    host = urlparse(url).netloc.replace("www.", "")
    name = host.split(".")[0].lower()  # e.g. "polymarket"

    sys.path.insert(0, str(BASE / "src"))
    # Try to fetch content for context
    content = ""
    try:
        from strategy_ai import fetch_content
        content = fetch_content(url)[:2000]
    except Exception as e:
        log.warning(f"fetch_content failed: {e}")

    # Generate adapter skeleton from template
    adapter_code = f'''"""
{name}_adapter.py — Auto-generated adapter for {url}
Generated by iEarnBot add_market at {datetime.utcnow().isoformat()}
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from adapters.base import MarketAdapter
from typing import Any, Dict, List


class {name.capitalize()}Adapter(MarketAdapter):
    """Adapter for {url}"""

    def __init__(self, trading_enabled: bool = False):
        super().__init__(trading_enabled=trading_enabled)
        self.base_url = "{url}"

    def get_markets(self, query: str = "") -> List[Dict[str, Any]]:
        raise NotImplementedError("get_markets not implemented for {name}")

    def get_price(self, market_id: str) -> Dict[str, float]:
        raise NotImplementedError("get_price not implemented for {name}")

    def get_positions(self) -> List[Dict[str, Any]]:
        raise NotImplementedError("get_positions not implemented for {name}")

    def get_balances(self) -> Dict[str, float]:
        raise NotImplementedError("get_balances not implemented for {name}")

    def _place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("_place_order not implemented for {name}")

    def _cancel_order(self, order_id: str) -> Dict[str, Any]:
        raise NotImplementedError("_cancel_order not implemented for {name}")

    def smoke_test(self) -> bool:
        try:
            self.get_markets()
            return True
        except NotImplementedError:
            return False
        except Exception:
            return False
'''

    adapter_path = BASE / "src" / "adapters" / f"{name}_adapter.py"
    adapter_path.write_text(adapter_code)

    # Write schema.json
    schema = {
        "name": name,
        "url": url,
        "adapter_file": f"{name}_adapter.py",
        "class": f"{name.capitalize()}Adapter",
        "generated_at": datetime.utcnow().isoformat(),
        "status": "skeleton",
    }
    schema_path = BASE / "src" / "adapters" / f"{name}_schema.json"
    schema_path.write_text(json.dumps(schema, indent=2))

    return {"name": name, "adapter_file": str(adapter_path), "schema_file": str(schema_path)}


def handle_list_markets(args: dict) -> dict:
    """读取 src/adapters/ 目录中的 *_schema.json 列表"""
    adapters_dir = BASE / "src" / "adapters"
    markets = []
    for fp in sorted(adapters_dir.glob("*schema*.json")):
        try:
            markets.append(json.loads(fp.read_text()))
        except Exception as e:
            log.warning(f"Failed to read {fp}: {e}")
    return {"markets": markets}


def handle_smoke_test(args: dict) -> dict:
    """调用对应 adapter.smoke_test()"""
    market = args.get("market", "polymarket")
    sys.path.insert(0, str(BASE / "src"))

    # Try to dynamically load the adapter
    adapters_dir = BASE / "src" / "adapters"
    adapter_file = adapters_dir / f"{market}_adapter.py"
    if not adapter_file.exists():
        raise FileNotFoundError(f"No adapter found for market: {market}")

    spec = importlib.util.spec_from_file_location(f"{market}_adapter", adapter_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Find the adapter class (first class ending in Adapter)
    adapter_cls = None
    for attr_name in dir(mod):
        obj = getattr(mod, attr_name)
        if (
            isinstance(obj, type)
            and attr_name.lower().endswith("adapter")
            and attr_name != "MarketAdapter"
        ):
            adapter_cls = obj
            break

    if adapter_cls is None:
        raise RuntimeError(f"No adapter class found in {adapter_file}")

    adapter = adapter_cls()
    result = adapter.smoke_test()
    return {"market": market, "smoke_test_passed": result}


def handle_get_strategy_params(args: dict) -> dict:
    """读取 data/strategies/{id}_params.yaml，返回 JSON 格式供 renderer 直接使用"""
    try:
        import yaml
    except ImportError:
        raise RuntimeError("PyYAML not installed; run: pip install pyyaml")

    strategy_id = args.get("strategy_id")
    if not strategy_id:
        raise ValueError("strategy_id is required")

    params_path = BASE / "data" / "strategies" / f"{strategy_id}_params.yaml"

    # If no params.yaml, try to load defaults from strategy JSON
    if not params_path.exists():
        strategy_path = BASE / "data" / "strategies" / f"{strategy_id}.json"
        if strategy_path.exists():
            try:
                strategy_data = json.loads(strategy_path.read_text())
                default_params = strategy_data.get("params", {})
                return {"strategy_id": strategy_id, "params": default_params, "source": "strategy_json"}
            except Exception as e:
                log.warning(f"Failed to read strategy JSON for {strategy_id}: {e}")
        return {"strategy_id": strategy_id, "params": {}, "note": "No params file found"}

    with params_path.open() as f:
        params = yaml.safe_load(f) or {}
    # Return as JSON-serializable dict (yaml.safe_load already produces Python primitives)
    return {"strategy_id": strategy_id, "params": params, "source": "params_yaml"}


def handle_fetch_url(args: dict) -> dict:
    """抓取 URL 内容并提取纯文本，供 strategy 生成使用"""
    url = args.get("url", "")
    if not url:
        raise ValueError("url is required")
    sys.path.insert(0, str(BASE / "src"))
    try:
        from strategy_ai import fetch_content
        text = fetch_content(url)
        return {"url": url, "text": text[:8000]}  # cap at 8k chars
    except Exception as e:
        raise RuntimeError(f"Failed to fetch {url}: {e}")


def handle_save_strategy_params(args: dict) -> dict:
    """写入 data/strategies/{id}_params.yaml"""
    try:
        import yaml
    except ImportError:
        raise RuntimeError("PyYAML not installed; run: pip install pyyaml")

    strategy_id = args.get("strategy_id")
    params = args.get("params", {})
    if not strategy_id:
        raise ValueError("strategy_id is required")

    params_dir = BASE / "data" / "strategies"
    params_dir.mkdir(parents=True, exist_ok=True)
    params_path = params_dir / f"{strategy_id}_params.yaml"

    with params_path.open("w") as f:
        yaml.safe_dump(params, f, allow_unicode=True, sort_keys=False)

    return {"strategy_id": strategy_id, "saved": True, "path": str(params_path)}


def handle_list_strategies(args: dict) -> dict:
    """读取 data/strategies/state.json"""
    state_path = BASE / "data" / "strategies" / "state.json"
    if not state_path.exists():
        return {"strategies": [], "note": "No state file found"}

    data = json.loads(state_path.read_text())
    # Accept both list and dict formats
    if isinstance(data, list):
        return {"strategies": data}
    return {"strategies": data.get("strategies", data)}


def handle_scheduler_status(args: dict) -> dict:
    """调用 scheduler.list_jobs()"""
    sched = _get_scheduler()
    jobs = sched.list_jobs()
    return {"jobs": jobs}


# ═══════════════════════════════════════════════════════════════════════════
# Dispatch table
# ═══════════════════════════════════════════════════════════════════════════

HANDLERS = {
    "get_balances":        handle_get_balances,
    "get_positions":       handle_get_positions,
    "generate_strategy":   handle_generate_strategy,
    "run_strategy":        handle_run_strategy,
    "stop_strategy":       handle_stop_strategy,
    "kill_switch":         handle_kill_switch,
    "get_logs":            handle_get_logs,
    "add_market":          handle_add_market,
    "list_markets":        handle_list_markets,
    "smoke_test":          handle_smoke_test,
    "fetch_url":           handle_fetch_url,
    "get_strategy_params": handle_get_strategy_params,
    "save_strategy_params":handle_save_strategy_params,
    "list_strategies":     handle_list_strategies,
    "scheduler_status":    handle_scheduler_status,
}


def handle(req: dict):
    req_id = req.get("id", "unknown")
    cmd = req.get("cmd", "")
    args = req.get("args", {})

    handler = HANDLERS.get(cmd)
    if handler is None:
        _reply(req_id, error=f"Unknown command: {cmd!r}. Available: {list(HANDLERS)}")
        return

    log.info(f"→ {cmd} (id={req_id})")
    try:
        result = handler(args)
        _reply(req_id, data=result)
        log.info(f"← {cmd} OK (id={req_id})")
    except Exception as e:
        log.exception(f"Handler error for cmd={cmd!r}: {e}")
        _reply(req_id, error=str(e))


# ═══════════════════════════════════════════════════════════════════════════
# Real-time log tail (bonus)
# ═══════════════════════════════════════════════════════════════════════════

_LEVEL_KEYWORDS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def _parse_level(line: str) -> str:
    upper = line.upper()
    for kw in _LEVEL_KEYWORDS:
        if kw in upper:
            return kw
    return "INFO"


def _tail_log_thread():
    """Background thread: tail data/logs/bot.log and push events to stdout."""
    log_path = BASE / "data" / "logs" / "bot.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Wait until file exists
    while not log_path.exists():
        time.sleep(2)

    log.info(f"Log-tail started: {log_path}")
    with log_path.open("r", errors="replace") as f:
        # Seek to end so we only push new lines
        f.seek(0, 2)
        while True:
            line = f.readline()
            if line:
                line = line.rstrip("\n")
                _emit(
                    {
                        "event": "log",
                        "level": _parse_level(line),
                        "msg": line,
                        "ts": datetime.utcnow().isoformat(),
                    }
                )
            else:
                time.sleep(0.25)


# ═══════════════════════════════════════════════════════════════════════════
# Main loop
# ═══════════════════════════════════════════════════════════════════════════

def main():
    log.info("IPC server started, waiting for commands on stdin...")

    # Start real-time log-tail in background
    t = threading.Thread(target=_tail_log_thread, daemon=True, name="log-tail")
    t.start()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            handle(req)
        except json.JSONDecodeError as e:
            log.error(f"JSON parse error: {e} — raw: {line!r}")
        except Exception as e:
            log.error(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
