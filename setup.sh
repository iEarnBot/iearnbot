#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  iEarn.Bot Setup Script
#  AI-Powered Prediction Market Bot — https://iearn.bot
# ═══════════════════════════════════════════════════════════════

set -e

BOLD="\033[1m"
GREEN="\033[32m"
ORANGE="\033[33m"
RED="\033[31m"
RESET="\033[0m"

INSTALL_DIR="$HOME/iearnbot"
ENV_FILE="$INSTALL_DIR/.env"

echo ""
echo -e "${BOLD}🔥 iEarn.Bot Installer${RESET}"
echo -e "   AI-Powered Prediction Market Bot"
echo -e "   https://iearn.bot"
echo ""

# ── Step 1: Python ─────────────────────────────────────────────
echo -e "${BOLD}[1/6] Checking Python...${RESET}"

# Try to find python 3.11+
PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3; do
  if command -v $cmd &>/dev/null; then
    VER=$($cmd -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    MAJ=$(echo $VER | cut -d. -f1)
    MIN=$(echo $VER | cut -d. -f2)
    if [ "$MAJ" -ge 3 ] && [ "$MIN" -ge 11 ]; then
      PYTHON=$cmd
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  echo -e "${RED}❌ Python 3.11+ not found (found $(python3 --version 2>/dev/null || echo 'none'))${RESET}"
  echo ""
  echo -e "  Please install Python 3.12 manually:"
  echo -e ""
  echo -e "  Option A — Download pkg installer (easiest):"
  echo -e "  ${BOLD}https://www.python.org/ftp/python/3.12.0/python-3.12.0-macos11.pkg${RESET}"
  echo -e ""
  echo -e "  Option B — Homebrew:"
  echo -e "  ${BOLD}brew install python@3.12${RESET}"
  echo -e ""
  echo -e "  After installing, re-run: ${BOLD}bash setup.sh${RESET}"
  exit 1
fi

PY_VERSION=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${GREEN}✅ Python $PY_VERSION ($PYTHON)${RESET}"

# ── Step 2: uv ─────────────────────────────────────────────────
echo -e "${BOLD}[2/6] Checking uv package manager...${RESET}"
if ! command -v uv &>/dev/null; then
  echo "   Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.cargo/bin:$PATH"
fi
echo -e "${GREEN}✅ uv $(uv --version 2>/dev/null | head -1)${RESET}"

# ── Step 3: Dependencies ────────────────────────────────────────
echo -e "${BOLD}[3/6] Installing dependencies...${RESET}"
cd "$INSTALL_DIR"
$PYTHON -m pip install -r requirements.txt --quiet
echo -e "${GREEN}✅ Dependencies installed${RESET}"

# ── Step 4: .env setup ─────────────────────────────────────────
echo -e "${BOLD}[4/6] Configuring .env...${RESET}"
if [ ! -f "$ENV_FILE" ]; then
  cp "$INSTALL_DIR/.env.example" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo ""
  echo -e "${ORANGE}  Please enter your configuration:${RESET}"
  echo ""

  read -s -p "  Polygon Private Key (0x...): " POLY_KEY; echo ""
  read -p "  SkillPay API Key (sk_...): " SP_KEY
  read -p "  Your User ID (Telegram ID or wallet address): " SP_UID

  sed -i.bak "s|POLYGON_PRIVATE_KEY=.*|POLYGON_PRIVATE_KEY=$POLY_KEY|" "$ENV_FILE"
  sed -i.bak "s|SKILLPAY_API_KEY=.*|SKILLPAY_API_KEY=$SP_KEY|" "$ENV_FILE"
  sed -i.bak "s|SKILLPAY_USER_ID=.*|SKILLPAY_USER_ID=$SP_UID|" "$ENV_FILE"
  rm -f "$ENV_FILE.bak"
  echo ""
  echo -e "${GREEN}✅ .env configured (chmod 600)${RESET}"
else
  echo -e "${GREEN}✅ .env already exists${RESET}"
fi

# ── Step 5: launchd (macOS auto-start) ─────────────────────────
echo -e "${BOLD}[5/6] Registering auto-start jobs (macOS)...${RESET}"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
mkdir -p "$LAUNCH_AGENTS"

# Ensure data directories exist (prevent risk.py crash on log write)
mkdir -p "$INSTALL_DIR/data/logs"

# Resolve full Python path for launchd (env vars not available in launchd context)
PYTHON_FULL=$(command -v $PYTHON)

# Fast job: every 5 min — take-profit + stop-loss
cat > "$LAUNCH_AGENTS/bot.iearnbot.fast.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>bot.iearnbot.fast</string>
  <key>ProgramArguments</key><array>
    <string>$PYTHON_FULL</string>
    <string>$INSTALL_DIR/src/risk.py</string>
  </array>
  <key>StartInterval</key><integer>300</integer>
  <key>WorkingDirectory</key><string>$INSTALL_DIR</string>
  <key>RunAtLoad</key><true/>
</dict></plist>
PLIST

# Mid job: every 15 min — V2/V3 strategies
cat > "$LAUNCH_AGENTS/bot.iearnbot.mid.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>bot.iearnbot.mid</string>
  <key>ProgramArguments</key><array>
    <string>$PYTHON_FULL</string>
    <string>$INSTALL_DIR/src/runner.py</string>
    <string>v2</string><string>v3</string>
  </array>
  <key>StartInterval</key><integer>900</integer>
  <key>WorkingDirectory</key><string>$INSTALL_DIR</string>
  <key>RunAtLoad</key><true/>
</dict></plist>
PLIST

# V1 job: every hour — V1 BTC momentum
cat > "$LAUNCH_AGENTS/bot.iearnbot.v1.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>bot.iearnbot.v1</string>
  <key>ProgramArguments</key><array>
    <string>$PYTHON_FULL</string>
    <string>$INSTALL_DIR/src/runner.py</string>
    <string>v1</string>
  </array>
  <key>StartInterval</key><integer>3600</integer>
  <key>WorkingDirectory</key><string>$INSTALL_DIR</string>
  <key>RunAtLoad</key><true/>
</dict></plist>
PLIST

launchctl load "$LAUNCH_AGENTS/bot.iearnbot.fast.plist" 2>/dev/null || true
launchctl load "$LAUNCH_AGENTS/bot.iearnbot.mid.plist"  2>/dev/null || true
launchctl load "$LAUNCH_AGENTS/bot.iearnbot.v1.plist"   2>/dev/null || true

echo -e "${GREEN}✅ launchd jobs registered (fast/mid/v1)${RESET}"

# ── Step 6: Dashboard ──────────────────────────────────────────
echo -e "${BOLD}[6/6] Starting Dashboard...${RESET}"
$PYTHON "$INSTALL_DIR/src/dashboard.py" &
sleep 2
echo -e "${GREEN}✅ Dashboard started → http://localhost:7799${RESET}"

# ── Done ───────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}🎉 iEarn.Bot is running!${RESET}"
echo ""
echo -e "  📊 Dashboard  → ${BOLD}http://localhost:7799${RESET}"
echo -e "  📁 Install    → ${BOLD}$INSTALL_DIR${RESET}"
echo -e "  📝 Logs       → ${BOLD}$INSTALL_DIR/data/logs/${RESET}"
echo -e "  🤖 AI Strategy → ${BOLD}python3 src/strategy_ai.py generate \"your idea\"${RESET}"
echo ""
echo -e "  ⚠️  Only use funds you can afford to lose. DYOR."
echo ""

# Auto-open browser
if command -v open &>/dev/null; then
  open "http://localhost:7799" 2>/dev/null || true
fi
