@echo off
REM build_exe.bat — Build iEarn.Bot Windows .exe
REM Requirements: Python 3.11+, pip install pyinstaller requests flask python-dotenv

setlocal
SET APP_NAME=iEarnBot
SET DIST_DIR=%~dp0dist
SET SCRIPT_DIR=%~dp0

echo 🔥 Building %APP_NAME% for Windows...

REM ── 1. Install deps ───────────────────────────────────────────────────────
pip install --quiet pyinstaller requests flask python-dotenv

REM ── 2. PyInstaller (one-file EXE, no console window) ─────────────────────
cd /d "%SCRIPT_DIR%"
pyinstaller ^
  --noconfirm ^
  --onefile ^
  --windowed ^
  --name "%APP_NAME%" ^
  --add-data "..\src;src" ^
  --hidden-import=flask ^
  --hidden-import=dotenv ^
  --hidden-import=requests ^
  --icon=iearnbot.ico ^
  main_win.py

IF NOT EXIST "%DIST_DIR%\%APP_NAME%.exe" (
  echo ❌ Build failed — %APP_NAME%.exe not found in %DIST_DIR%
  exit /b 1
)

echo.
echo ✅ EXE ready: %DIST_DIR%\%APP_NAME%.exe
echo    Run the installer and follow on-screen instructions.
endlocal
