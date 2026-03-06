"""
main_win.py — iEarn.Bot System Tray App (Windows)
Requires: pystray, Pillow, requests, flask, python-dotenv

Install: pip install pystray Pillow requests flask python-dotenv
"""
import sys
import os
import subprocess
import threading
import webbrowser
import time
from pathlib import Path

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    print("ERROR: pystray and Pillow are required. Run: pip install pystray Pillow")
    sys.exit(1)

BASE = Path(__file__).parent.parent
DASHBOARD_URL = "http://localhost:7799"
RUNNER_SCRIPT = BASE / "src" / "runner.py"
DASHBOARD_SCRIPT = BASE / "src" / "dashboard.py"

_bot_process = None
_dashboard_process = None


def make_icon_image():
    """Create a simple flame-colored icon for the system tray."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Draw a simple orange circle as placeholder icon
    draw.ellipse([4, 4, 60, 60], fill=(249, 115, 22, 255))
    draw.text((20, 18), "🔥", fill=(255, 255, 255, 255))
    return img


def start_dashboard():
    global _dashboard_process
    if _dashboard_process and _dashboard_process.poll() is None:
        return
    _dashboard_process = subprocess.Popen(
        [sys.executable, str(DASHBOARD_SCRIPT)],
        cwd=str(BASE),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )


def stop_dashboard():
    global _dashboard_process
    if _dashboard_process and _dashboard_process.poll() is None:
        _dashboard_process.terminate()
    _dashboard_process = None


def open_browser_after_delay(delay=1.5):
    def _open():
        time.sleep(delay)
        webbrowser.open(DASHBOARD_URL)
    threading.Thread(target=_open, daemon=True).start()


# ── Menu actions ──────────────────────────────────────────────────────────

def on_start_bot(icon, item):
    global _bot_process
    if _bot_process and _bot_process.poll() is None:
        return
    _bot_process = subprocess.Popen(
        [sys.executable, str(RUNNER_SCRIPT), "v1", "v2"],
        cwd=str(BASE),
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )


def on_stop_bot(icon, item):
    global _bot_process
    if _bot_process and _bot_process.poll() is None:
        _bot_process.terminate()
        _bot_process = None


def on_open_dashboard(icon, item):
    webbrowser.open(DASHBOARD_URL)


def on_check_balance(icon, item):
    try:
        import requests as req
        r = req.get(f"{DASHBOARD_URL}/api/status", timeout=5)
        data = r.json()
        bal = data.get("skillpay_balance", "N/A")
        # Windows toast via win10toast if available, else print
        try:
            from win10toast import ToastNotifier
            ToastNotifier().show_toast(
                "iEarn.Bot — Balance",
                f"SkillPay: {bal} USDT",
                duration=5,
                threaded=True,
            )
        except Exception:
            print(f"SkillPay Balance: {bal} USDT")
    except Exception as e:
        print(f"Balance check failed: {e}")


def on_quit(icon, item):
    on_stop_bot(icon, item)
    stop_dashboard()
    icon.stop()


# ── Entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    start_dashboard()
    open_browser_after_delay(2.0)

    menu = pystray.Menu(
        pystray.MenuItem("▶ Start Bot", on_start_bot),
        pystray.MenuItem("⏹ Stop Bot", on_stop_bot),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("📊 Open Dashboard", on_open_dashboard),
        pystray.MenuItem("💳 Check Balance", on_check_balance),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit iEarn.Bot", on_quit),
    )

    icon = pystray.Icon(
        "iEarn.Bot",
        make_icon_image(),
        "🔥 iEarn.Bot",
        menu,
    )
    icon.run()
