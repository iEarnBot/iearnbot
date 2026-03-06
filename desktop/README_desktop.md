# 🖥️ iEarn.Bot Desktop App

Run iEarn.Bot as a native desktop application — **no terminal required**.

---

## macOS (.dmg)

### Requirements
- macOS 12 Monterey or later
- Python 3.11+ (for building from source)

### Install (pre-built)
1. Download `iEarnBot-v0.1-macOS.dmg` from [Releases](https://github.com/iEarnBot/iearnbot/releases)
2. Open the DMG and drag **iEarn.Bot** to your Applications folder
3. Launch from Spotlight (`⌘ Space → iEarn.Bot`) or Applications
4. A 🔥 icon appears in your **menu bar** — click it to control the bot

### Build from source
```bash
cd desktop
pip install pyinstaller rumps pyobjc-framework-Cocoa requests flask python-dotenv
brew install create-dmg
bash build_dmg.sh
```

### Menu bar options
| Item | Action |
|------|--------|
| ▶ Start Bot | Runs V1 + V2 strategies |
| ⏹ Stop Bot | Stops all running strategies |
| 📊 Open Dashboard | Opens http://localhost:7799 in browser |
| 💳 Check Balance | Shows SkillPay USDT balance (notification) |
| Quit iEarn.Bot | Stops bot + dashboard, exits cleanly |

---

## Windows (.exe)

### Requirements
- Windows 10 / 11 (64-bit)
- Python 3.11+ (for building from source)

### Install (pre-built)
1. Download `iEarnBot-v0.1-Windows.exe` from [Releases](https://github.com/iEarnBot/iearnbot/releases)
2. Double-click to run — Windows SmartScreen may warn on first launch; click **More info → Run anyway**
3. A 🔥 icon appears in the **system tray** (bottom-right)
4. Right-click the icon to control the bot

### Build from source
```powershell
cd desktop
pip install pyinstaller pystray Pillow requests flask python-dotenv
build_exe.bat
```

> **Tip:** Add your `.env` file next to the `.exe` before the first run.

---

## First-time setup

After launching, open the **dashboard** (📊) and:
1. Configure your wallet key and SkillPay API key via **Settings**
2. Click **Start Bot** to begin trading

Config file location:
- macOS: `~/iearnbot/.env`
- Windows: `%USERPROFILE%\iearnbot\.env`

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| App won't open on macOS | `System Settings → Privacy & Security → Open Anyway` |
| Dashboard doesn't load | Wait 3–5 s, then click 📊 again |
| "Not running" on Stop | Bot may have already exited; check dashboard logs |
| Windows Defender blocks | Whitelist the EXE in Windows Security |

---

## Uninstall

- **macOS:** Drag `iEarn.Bot.app` from Applications to Trash
- **Windows:** Delete `iEarnBot.exe` and `%USERPROFILE%\iearnbot\`
