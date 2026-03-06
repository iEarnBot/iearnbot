"""
desktop/main.py — iEarn.Bot System Tray App (macOS)
Requires: rumps, webbrowser (stdlib)

Install: pip install rumps pyobjc-framework-Cocoa
"""
import rumps
import subprocess
import sys
import os
import threading
import webbrowser
import time
from pathlib import Path

BASE = Path(__file__).parent.parent
DASHBOARD_URL = "http://localhost:7799"
RUNNER_SCRIPT = BASE / "src" / "runner.py"
DASHBOARD_SCRIPT = BASE / "src" / "dashboard.py"

_bot_process = None
_dashboard_process = None
_dashboard_started = False


def start_dashboard():
    """Start the Flask dashboard in a background process."""
    global _dashboard_process, _dashboard_started
    if _dashboard_process and _dashboard_process.poll() is None:
        return  # already running
    _dashboard_process = subprocess.Popen(
        [sys.executable, str(DASHBOARD_SCRIPT)],
        cwd=str(BASE),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _dashboard_started = True


def stop_dashboard():
    global _dashboard_process, _dashboard_started
    if _dashboard_process and _dashboard_process.poll() is None:
        _dashboard_process.terminate()
    _dashboard_process = None
    _dashboard_started = False


def open_browser_after_delay(delay=1.5):
    """Open browser to dashboard after a short delay (let Flask start up)."""
    def _open():
        time.sleep(delay)
        webbrowser.open(DASHBOARD_URL)
    threading.Thread(target=_open, daemon=True).start()


class IEarnBotApp(rumps.App):
    def __init__(self):
        super().__init__(
            "🔥",
            title="🔥 iEarn.Bot",
            quit_button=None,  # we add our own Quit
        )
        self.menu = [
            rumps.MenuItem("▶  Start Bot", callback=self.start_bot),
            rumps.MenuItem("⏹  Stop Bot", callback=self.stop_bot),
            None,  # separator
            rumps.MenuItem("📊  Open Dashboard", callback=self.open_dashboard),
            rumps.MenuItem("💳  Check Balance", callback=self.check_balance),
            None,  # separator
            rumps.MenuItem("Quit iEarn.Bot", callback=self.quit_app),
        ]
        # Auto-open dashboard on launch
        start_dashboard()
        open_browser_after_delay(2.0)

    # ---- Bot control -------------------------------------------------------

    @rumps.clicked("▶  Start Bot")
    def start_bot(self, _):
        global _bot_process
        if _bot_process and _bot_process.poll() is None:
            rumps.notification(
                "iEarn.Bot",
                "Already running",
                "The bot is already active.",
                sound=False,
            )
            return
        _bot_process = subprocess.Popen(
            [sys.executable, str(RUNNER_SCRIPT), "v1", "v2"],
            cwd=str(BASE),
        )
        rumps.notification(
            "iEarn.Bot",
            "Bot Started 🚀",
            "Strategies V1 + V2 are now running.",
            sound=False,
        )

    @rumps.clicked("⏹  Stop Bot")
    def stop_bot(self, _):
        global _bot_process
        if _bot_process and _bot_process.poll() is None:
            _bot_process.terminate()
            _bot_process = None
            rumps.notification(
                "iEarn.Bot",
                "Bot Stopped",
                "All strategies have been stopped.",
                sound=False,
            )
        else:
            rumps.notification(
                "iEarn.Bot",
                "Not running",
                "The bot is not currently active.",
                sound=False,
            )

    # ---- Dashboard ---------------------------------------------------------

    @rumps.clicked("📊  Open Dashboard")
    def open_dashboard(self, _):
        if not _dashboard_started:
            start_dashboard()
            open_browser_after_delay(1.5)
        else:
            webbrowser.open(DASHBOARD_URL)

    # ---- Balance -----------------------------------------------------------

    @rumps.clicked("💳  Check Balance")
    def check_balance(self, _):
        try:
            import requests
            r = requests.get(f"{DASHBOARD_URL}/api/status", timeout=5)
            data = r.json()
            bal = data.get("skillpay_balance", "N/A")
            rumps.notification(
                "iEarn.Bot — Balance",
                f"SkillPay: {bal} USDT",
                "Top up at skillpay.me if needed.",
                sound=False,
            )
        except Exception as e:
            rumps.notification(
                "iEarn.Bot",
                "Balance check failed",
                f"Dashboard may not be running. ({e})",
                sound=False,
            )

    # ---- Quit --------------------------------------------------------------

    @rumps.clicked("Quit iEarn.Bot")
    def quit_app(self, _):
        global _bot_process
        if _bot_process and _bot_process.poll() is None:
            _bot_process.terminate()
        stop_dashboard()
        rumps.quit_application()


if __name__ == "__main__":
    IEarnBotApp().run()
