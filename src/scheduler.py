"""
scheduler.py — iEranBot Strategy Scheduler
支持: manual / interval / cron 三种调度模式
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import json, logging, os, sys, time
from datetime import datetime
from pathlib import Path

log = logging.getLogger("scheduler")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

BASE = Path(__file__).parent.parent
KILL_SWITCH_FLAG = BASE / "data" / "risk" / "kill_switch.flag"
JOBS_STATE_FILE = BASE / "data" / "scheduler" / "jobs.json"


def _check_kill_switch(strategy_id: str) -> bool:
    """Returns True if kill-switch is active (job should be skipped)."""
    if KILL_SWITCH_FLAG.exists():
        log.warning(f"[KILL-SWITCH] strategy {strategy_id} skipped")
        return True
    return False


def _make_dummy_runner(strategy_id: str):
    """Create a placeholder runner for CLI-restored jobs (no real runner_fn)."""
    def runner():
        if _check_kill_switch(strategy_id):
            return
        log.info(f"[RUN] strategy {strategy_id} executed (dummy runner)")
    return runner


class StrategyScheduler:
    def __init__(self):
        self._scheduler = BackgroundScheduler()
        # Map strategy_id -> {runner_fn, schedule, enabled}
        self._registry: dict[str, dict] = {}
        JOBS_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    def _build_trigger(self, schedule: dict):
        """Build an APScheduler trigger from a schedule dict."""
        mode = schedule.get("mode", "manual")
        if mode == "manual":
            return None
        elif mode == "interval":
            every = int(schedule.get("every", 1))
            unit = schedule.get("unit", "minutes")
            if unit == "months":
                # Simulate monthly with cron: day=1, every month
                return CronTrigger(day=1)
            kwargs = {unit: every}
            return IntervalTrigger(**kwargs)
        elif mode == "cron":
            cron_expr = schedule.get("cron", "* * * * *")
            parts = cron_expr.split()
            if len(parts) == 5:
                minute, hour, day, month, day_of_week = parts
                return CronTrigger(
                    minute=minute,
                    hour=hour,
                    day=day,
                    month=month,
                    day_of_week=day_of_week,
                )
            else:
                raise ValueError(f"Invalid cron expression: {cron_expr}")
        else:
            raise ValueError(f"Unknown schedule mode: {mode}")

    def _wrapped_runner(self, strategy_id: str, runner_fn):
        """Wrap runner_fn with kill-switch check and last_run update."""
        def job():
            if _check_kill_switch(strategy_id):
                return
            log.info(f"[RUN] executing strategy {strategy_id}")
            try:
                runner_fn()
                last_run = datetime.now().isoformat(timespec="seconds")
                if strategy_id in self._registry:
                    self._registry[strategy_id]["last_run"] = last_run
                self._save_state()
                log.info(f"[RUN] strategy {strategy_id} completed")
            except Exception as e:
                log.error(f"[RUN] strategy {strategy_id} failed: {e}")
        return job

    def _save_state(self):
        """Persist current job states to JOBS_STATE_FILE."""
        state = {}
        for sid, info in self._registry.items():
            state[sid] = {
                "schedule": info["schedule"],
                "enabled": info.get("enabled", True),
                "last_run": info.get("last_run"),
            }
        JOBS_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(JOBS_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    def _load_state(self) -> dict:
        """Load persisted job states."""
        if JOBS_STATE_FILE.exists():
            try:
                with open(JOBS_STATE_FILE) as f:
                    return json.load(f)
            except Exception as e:
                log.warning(f"Failed to load jobs state: {e}")
        return {}

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def add_strategy(self, strategy_id: str, runner_fn, schedule: dict):
        """Register and schedule a strategy."""
        trigger = self._build_trigger(schedule)
        wrapped = self._wrapped_runner(strategy_id, runner_fn)

        self._registry[strategy_id] = {
            "runner_fn": runner_fn,
            "schedule": schedule,
            "enabled": True,
            "last_run": None,
        }

        if trigger is not None:
            if self._scheduler.get_job(strategy_id):
                self._scheduler.remove_job(strategy_id)
            self._scheduler.add_job(wrapped, trigger=trigger, id=strategy_id, replace_existing=True)
            log.info(f"[SCHEDULER] added job {strategy_id} with trigger {trigger}")
        else:
            log.info(f"[SCHEDULER] added manual-only strategy {strategy_id} (no trigger)")

        self._save_state()

    def run_now(self, strategy_id: str):
        """Manually trigger immediate execution of a strategy."""
        if strategy_id not in self._registry:
            log.error(f"[RUN-NOW] strategy {strategy_id} not found")
            return
        info = self._registry[strategy_id]
        runner_fn = info.get("runner_fn") or _make_dummy_runner(strategy_id)
        wrapped = self._wrapped_runner(strategy_id, runner_fn)
        log.info(f"[RUN-NOW] triggering {strategy_id}")
        wrapped()

    def pause_strategy(self, strategy_id: str):
        """Pause a scheduled strategy."""
        job = self._scheduler.get_job(strategy_id)
        if job:
            job.pause()
            log.info(f"[SCHEDULER] paused {strategy_id}")
        if strategy_id in self._registry:
            self._registry[strategy_id]["enabled"] = False
            self._save_state()
        else:
            log.warning(f"[SCHEDULER] pause: strategy {strategy_id} not in registry")

    def resume_strategy(self, strategy_id: str):
        """Resume a paused strategy."""
        job = self._scheduler.get_job(strategy_id)
        if job:
            job.resume()
            log.info(f"[SCHEDULER] resumed {strategy_id}")
        if strategy_id in self._registry:
            self._registry[strategy_id]["enabled"] = True
            self._save_state()
        else:
            log.warning(f"[SCHEDULER] resume: strategy {strategy_id} not in registry")

    def remove_strategy(self, strategy_id: str):
        """Remove a strategy from the scheduler."""
        job = self._scheduler.get_job(strategy_id)
        if job:
            self._scheduler.remove_job(strategy_id)
            log.info(f"[SCHEDULER] removed job {strategy_id}")
        if strategy_id in self._registry:
            del self._registry[strategy_id]
            self._save_state()
        else:
            log.warning(f"[SCHEDULER] remove: strategy {strategy_id} not found")

    def list_jobs(self) -> list[dict]:
        """Return a list of all job statuses."""
        result = []
        for sid, info in self._registry.items():
            job = self._scheduler.get_job(sid)
            next_run = None
            if job and job.next_run_time:
                next_run = job.next_run_time.isoformat(timespec="seconds")
            result.append({
                "strategy_id": sid,
                "schedule": info["schedule"],
                "enabled": info.get("enabled", True),
                "last_run": info.get("last_run"),
                "next_run": next_run,
            })
        return result

    def start(self):
        """Start the scheduler and restore persisted jobs."""
        state = self._load_state()
        for sid, info in state.items():
            schedule = info.get("schedule", {"mode": "manual"})
            runner_fn = _make_dummy_runner(sid)
            self._registry[sid] = {
                "runner_fn": runner_fn,
                "schedule": schedule,
                "enabled": info.get("enabled", True),
                "last_run": info.get("last_run"),
            }
            trigger = self._build_trigger(schedule)
            if trigger is not None:
                wrapped = self._wrapped_runner(sid, runner_fn)
                self._scheduler.add_job(wrapped, trigger=trigger, id=sid, replace_existing=True)
                if not info.get("enabled", True):
                    self._scheduler.get_job(sid).pause()
            log.info(f"[SCHEDULER] restored job {sid} ({schedule})")

        self._scheduler.start()
        log.info("[SCHEDULER] started")

    def shutdown(self):
        """Shutdown the scheduler gracefully."""
        self._scheduler.shutdown(wait=False)
        log.info("[SCHEDULER] shutdown")


# ------------------------------------------------------------------ #
#  CLI entry point
# ------------------------------------------------------------------ #

def _cli_scheduler() -> StrategyScheduler:
    """Return a scheduler with state loaded (for CLI ops)."""
    s = StrategyScheduler()
    state = s._load_state()
    for sid, info in state.items():
        schedule = info.get("schedule", {"mode": "manual"})
        runner_fn = _make_dummy_runner(sid)
        s._registry[sid] = {
            "runner_fn": runner_fn,
            "schedule": schedule,
            "enabled": info.get("enabled", True),
            "last_run": info.get("last_run"),
        }
    return s


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python src/scheduler.py <command> [args]")
        print("Commands: start | run-now <id> | add <id> interval <n> <unit> | add <id> cron <expr> | list | pause <id> | resume <id> | remove <id>")
        sys.exit(1)

    cmd = args[0]

    if cmd == "start":
        s = StrategyScheduler()
        s.start()
        print("[SCHEDULER] running — Ctrl+C to stop")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            s.shutdown()
            print("[SCHEDULER] stopped")

    elif cmd == "run-now":
        if len(args) < 2:
            print("Usage: run-now <strategy_id>")
            sys.exit(1)
        sid = args[1]
        s = _cli_scheduler()
        if sid not in s._registry:
            print(f"[ERROR] strategy {sid} not found in jobs.json")
            sys.exit(1)
        s.run_now(sid)

    elif cmd == "add":
        # add <id> interval <n> <unit>
        # add <id> cron <expr>
        if len(args) < 4:
            print("Usage: add <id> interval <n> <unit> | add <id> cron <expr>")
            sys.exit(1)
        sid = args[1]
        mode = args[2]
        if mode == "interval":
            if len(args) < 5:
                print("Usage: add <id> interval <n> <unit>")
                sys.exit(1)
            every = int(args[3])
            unit = args[4]
            schedule = {"mode": "interval", "every": every, "unit": unit}
        elif mode == "cron":
            cron_expr = args[3]
            schedule = {"mode": "cron", "cron": cron_expr}
        elif mode == "manual":
            schedule = {"mode": "manual"}
        else:
            print(f"Unknown mode: {mode}")
            sys.exit(1)
        s = _cli_scheduler()
        runner_fn = _make_dummy_runner(sid)
        s.add_strategy(sid, runner_fn, schedule)
        print(f"[SCHEDULER] added strategy {sid} with schedule {schedule}")

    elif cmd == "list":
        s = _cli_scheduler()
        # For list, we need the scheduler running briefly to get next_run
        s._scheduler.start()
        jobs = s.list_jobs()
        s._scheduler.shutdown(wait=False)
        if not jobs:
            print("No jobs registered.")
        else:
            print(f"{'ID':<15} {'Mode':<10} {'Schedule':<30} {'Enabled':<8} {'Last Run':<22} {'Next Run'}")
            print("-" * 100)
            for j in jobs:
                sch = j["schedule"]
                mode = sch.get("mode", "?")
                if mode == "interval":
                    sch_str = f"every {sch.get('every')} {sch.get('unit')}"
                elif mode == "cron":
                    sch_str = f"cron: {sch.get('cron')}"
                else:
                    sch_str = "manual"
                print(f"{j['strategy_id']:<15} {mode:<10} {sch_str:<30} {str(j['enabled']):<8} {str(j['last_run'] or '-'):<22} {j['next_run'] or '-'}")

    elif cmd == "pause":
        if len(args) < 2:
            print("Usage: pause <strategy_id>")
            sys.exit(1)
        sid = args[1]
        s = _cli_scheduler()
        s._scheduler.start()
        s.pause_strategy(sid)
        s._scheduler.shutdown(wait=False)
        print(f"[SCHEDULER] paused {sid}")

    elif cmd == "resume":
        if len(args) < 2:
            print("Usage: resume <strategy_id>")
            sys.exit(1)
        sid = args[1]
        s = _cli_scheduler()
        s._scheduler.start()
        s.resume_strategy(sid)
        s._scheduler.shutdown(wait=False)
        print(f"[SCHEDULER] resumed {sid}")

    elif cmd == "remove":
        if len(args) < 2:
            print("Usage: remove <strategy_id>")
            sys.exit(1)
        sid = args[1]
        s = _cli_scheduler()
        s._scheduler.start()
        s.remove_strategy(sid)
        s._scheduler.shutdown(wait=False)
        print(f"[SCHEDULER] removed {sid}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
