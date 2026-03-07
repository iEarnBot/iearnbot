const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage, shell } = require('electron');
const { execFile, spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

let mainWindow = null;
let tray = null;
let pythonProcess = null;   // legacy one-shot process (python:run)
let pyProcess = null;       // persistent IPC server process
let pythonPath = 'python3';

// ──────────────────────────────────────────────
// Python path detection
// ──────────────────────────────────────────────
function detectPython() {
  return new Promise((resolve) => {
    execFile('which', ['python3'], (err, stdout) => {
      if (!err && stdout.trim()) {
        pythonPath = stdout.trim();
        resolve(pythonPath);
      } else {
        execFile('which', ['python'], (err2, stdout2) => {
          if (!err2 && stdout2.trim()) {
            pythonPath = stdout2.trim();
          }
          resolve(pythonPath);
        });
      }
    });
  });
}

// ──────────────────────────────────────────────
// Window creation
// ──────────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 720,
    minWidth: 800,
    minHeight: 600,
    backgroundColor: '#080c14',
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
    icon: path.join(__dirname, 'assets', process.platform === 'win32' ? 'icon.ico' : 'icon.icns'),
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Dev tools in dev mode
  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools();
  }
}

// ──────────────────────────────────────────────
// Tray
// ──────────────────────────────────────────────
function createTray() {
  const iconPath = path.join(__dirname, 'assets', 'tray.png');
  let trayIcon;
  if (fs.existsSync(iconPath)) {
    trayIcon = nativeImage.createFromPath(iconPath);
  } else {
    // 1x1 fallback (must be non-empty for Tray)
    trayIcon = nativeImage.createFromDataURL(
      'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII='
    );
  }

  tray = new Tray(trayIcon);
  tray.setToolTip('iEarn.Bot');

  const contextMenu = Menu.buildFromTemplate([
    { label: 'Show iEarn.Bot', click: () => { if (mainWindow) mainWindow.show(); else createWindow(); } },
    { type: 'separator' },
    { label: 'Quit', click: () => app.quit() },
  ]);

  tray.setContextMenu(contextMenu);
  tray.on('click', () => {
    if (mainWindow) {
      mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show();
    }
  });
}

// ──────────────────────────────────────────────
// Persistent Python IPC server
// ──────────────────────────────────────────────
function startPythonIPC() {
  const scriptPath = path.join(__dirname, '..', 'src', 'ipc_server.py');
  pyProcess = spawn(pythonPath, [scriptPath], {
    cwd: path.join(__dirname, '..'),
    env: { ...process.env, PYTHONPATH: path.join(__dirname, '..', 'src') },
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  pyProcess.stdout.on('data', (data) => {
    // Parse JSON lines and broadcast push-events (no id) to all renderer windows
    data.toString().split('\n').filter(Boolean).forEach(line => {
      try {
        const msg = JSON.parse(line);
        // Only broadcast push events (not request responses — those are handled per-request)
        if (msg.event) {
          BrowserWindow.getAllWindows().forEach(win => {
            win.webContents.send('py:message', msg);
          });
        }
      } catch (e) {}
    });
  });

  pyProcess.stderr.on('data', (data) => {
    console.log('[Python IPC]', data.toString());
  });

  pyProcess.on('exit', (code) => {
    console.log('[Python IPC] exited with code:', code);
    pyProcess = null;
  });

  pyProcess.on('error', (err) => {
    console.error('[Python IPC] spawn error:', err);
    pyProcess = null;
  });

  console.log('[main] Python IPC server started, pid:', pyProcess.pid);
}

// IPC: send command to persistent Python IPC server
ipcMain.handle('py:send', (_, cmd) => {
  return new Promise((resolve, reject) => {
    if (!pyProcess) return reject(new Error('Python IPC server not running'));
    const id = cmd.id || `req-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    cmd.id = id;

    let timeoutHandle = null;

    const handler = (data) => {
      data.toString().split('\n').filter(Boolean).forEach(line => {
        try {
          const msg = JSON.parse(line);
          if (msg.id === id) {
            if (timeoutHandle) clearTimeout(timeoutHandle);
            pyProcess.stdout.removeListener('data', handler);
            if (msg.ok) {
              resolve(msg);
            } else {
              reject(new Error(msg.error || 'Unknown error'));
            }
          }
        } catch (e) {}
      });
    };

    pyProcess.stdout.on('data', handler);
    pyProcess.stdin.write(JSON.stringify(cmd) + '\n');

    // Timeout after 30s
    timeoutHandle = setTimeout(() => {
      pyProcess.stdout.removeListener('data', handler);
      reject(new Error('py:send timeout for cmd: ' + cmd.cmd));
    }, 30000);
  });
});

// ──────────────────────────────────────────────
// IPC: Python subprocess (legacy one-shot)
// ──────────────────────────────────────────────
ipcMain.handle('python:run', async (event, args) => {
  return new Promise((resolve, reject) => {
    if (pythonProcess) {
      return reject(new Error('Python process already running'));
    }

    const scriptArgs = Array.isArray(args) ? args : [args];
    pythonProcess = spawn(pythonPath, scriptArgs, {
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';

    pythonProcess.stdout.on('data', (data) => {
      const line = data.toString();
      stdout += line;
      // Stream each line as a log event
      if (mainWindow) {
        mainWindow.webContents.send('log:line', { level: 'INFO', text: line.trim(), ts: Date.now() });
      }
    });

    pythonProcess.stderr.on('data', (data) => {
      const line = data.toString();
      stderr += line;
      if (mainWindow) {
        mainWindow.webContents.send('log:line', { level: 'ERROR', text: line.trim(), ts: Date.now() });
      }
    });

    pythonProcess.on('close', (code) => {
      pythonProcess = null;
      resolve({ code, stdout, stderr });
    });

    pythonProcess.on('error', (err) => {
      pythonProcess = null;
      reject(err);
    });
  });
});

ipcMain.handle('python:stop', async () => {
  if (pythonProcess) {
    pythonProcess.kill('SIGTERM');
    pythonProcess = null;
    return { ok: true };
  }
  return { ok: false, reason: 'No process running' };
});

ipcMain.handle('python:status', async () => {
  return { running: pythonProcess !== null, pid: pythonProcess?.pid ?? null };
});

// ──────────────────────────────────────────────
// IPC: File system (sandboxed to workspace)
// ──────────────────────────────────────────────
const WORKSPACE_ROOT = path.join(os.homedir(), '.openclaw', 'workspace');

function safePath(filePath) {
  const resolved = path.resolve(filePath);
  if (!resolved.startsWith(WORKSPACE_ROOT) && !resolved.startsWith(os.tmpdir())) {
    throw new Error(`Access denied: ${filePath}`);
  }
  return resolved;
}

ipcMain.handle('fs:readFile', async (event, filePath) => {
  const safe = safePath(filePath);
  return fs.promises.readFile(safe, 'utf8');
});

ipcMain.handle('fs:writeFile', async (event, filePath, data) => {
  const safe = safePath(filePath);
  await fs.promises.mkdir(path.dirname(safe), { recursive: true });
  await fs.promises.writeFile(safe, data, 'utf8');
  return { ok: true };
});

// ──────────────────────────────────────────────
// IPC: Keychain (macOS keytar)
// ──────────────────────────────────────────────
let keytar = null;
try {
  keytar = require('keytar');
} catch {
  console.warn('[main] keytar not available — falling back to in-memory store');
}

const memStore = {};

ipcMain.handle('keychain:set', async (event, key, value) => {
  if (keytar) {
    await keytar.setPassword('iearnbot', key, value);
  } else {
    memStore[key] = value;
  }
  return { ok: true };
});

ipcMain.handle('keychain:get', async (event, key) => {
  if (keytar) {
    return keytar.getPassword('iearnbot', key);
  }
  return memStore[key] ?? null;
});

// ──────────────────────────────────────────────
// App lifecycle
// ──────────────────────────────────────────────
app.whenReady().then(async () => {
  await detectPython();
  console.log(`[main] Python path: ${pythonPath}`);
  startPythonIPC();
  createWindow();
  if (process.platform === 'darwin') {
    createTray();
    app.dock.show();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

app.on('before-quit', () => {
  if (pythonProcess) pythonProcess.kill('SIGTERM');
  if (pyProcess) pyProcess.kill('SIGTERM');
});
