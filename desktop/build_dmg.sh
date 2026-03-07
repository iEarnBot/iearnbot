#!/usr/bin/env bash
# build_dmg.sh — Build iEarn.Bot macOS .dmg
#
# v0.4+: Uses Electron + electron-builder (arm64 + x64)
# Requirements:
#   node/npm (electron-builder is installed via npm)
#   cd electron && npm install

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
ELECTRON_DIR="$REPO_ROOT/electron"
DIST_DIR="$ELECTRON_DIR/dist"
APP_NAME="iEarn.Bot"

echo "🔥 Building $APP_NAME (Electron) .dmg packages..."

# ── 1. Install npm deps ────────────────────────────────────────────────────
cd "$ELECTRON_DIR"
npm install

# ── 2. Build arm64 DMG ────────────────────────────────────────────────────
echo "📦 Building arm64 DMG..."
npx electron-builder --mac dmg --arm64

# ── 3. Build x64 DMG ──────────────────────────────────────────────────────
echo "📦 Building x64 DMG..."
npx electron-builder --mac dmg --x64

# ── 4. Verify output ──────────────────────────────────────────────────────
echo ""
echo "✅ DMG packages ready:"
ls -lh "$DIST_DIR"/*.dmg

echo ""
echo "   arm64 (Apple Silicon): $DIST_DIR/iEarn.Bot-*-arm64.dmg"
echo "   x64   (Intel):         $DIST_DIR/iEarn.Bot-*.dmg"
echo "   Drag '$APP_NAME.app' to Applications and launch from Spotlight."
