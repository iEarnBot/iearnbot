#!/usr/bin/env bash
# build_dmg.sh — Build iEarn.Bot macOS .dmg
# Requirements:
#   pip install pyinstaller rumps pyobjc-framework-Cocoa requests flask python-dotenv
#   brew install create-dmg

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$SCRIPT_DIR/dist"
APP_NAME="iEarn.Bot"
DMG_NAME="iEarnBot-v0.1-macOS"

echo "🔥 Building $APP_NAME desktop app..."

# ── 1. Install Python deps ─────────────────────────────────────────────────
pip install --quiet pyinstaller rumps pyobjc-framework-Cocoa requests flask python-dotenv

# ── 2. PyInstaller ─────────────────────────────────────────────────────────
cd "$SCRIPT_DIR"
pyinstaller --noconfirm iearnbot.spec

# ── 3. Verify .app bundle ──────────────────────────────────────────────────
APP_PATH="$DIST_DIR/$APP_NAME.app"
if [ ! -d "$APP_PATH" ]; then
  echo "❌ Build failed — $APP_PATH not found"
  exit 1
fi
echo "✅ App bundle: $APP_PATH"

# ── 4. Create DMG ──────────────────────────────────────────────────────────
DMG_OUT="$SCRIPT_DIR/$DMG_NAME.dmg"
rm -f "$DMG_OUT"

create-dmg \
  --volname "$APP_NAME" \
  --volicon "$APP_PATH/Contents/Resources/app.icns" 2>/dev/null || true \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 128 \
  --icon "$APP_NAME.app" 170 190 \
  --hide-extension "$APP_NAME.app" \
  --app-drop-link 430 190 \
  --no-internet-enable \
  "$DMG_OUT" \
  "$APP_PATH" \
  || \
  create-dmg \
    --volname "$APP_NAME" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 128 \
    --icon "$APP_NAME.app" 170 190 \
    --app-drop-link 430 190 \
    "$DMG_OUT" \
    "$APP_PATH"

echo ""
echo "✅ DMG ready: $DMG_OUT"
echo "   Drag '$APP_NAME.app' to Applications and launch from Spotlight."
