const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('ipcApi', {
  // Python subprocess (legacy one-shot)
  runPython: (args) => ipcRenderer.invoke('python:run', args),
  stopPython: () => ipcRenderer.invoke('python:stop'),
  pythonStatus: () => ipcRenderer.invoke('python:status'),

  // Persistent Python IPC server
  pyCmd: (cmd) => ipcRenderer.invoke('py:send', cmd),
  onPyEvent: (cb) => ipcRenderer.on('py:message', (_, msg) => cb(msg)),

  // File system
  readFile: (filePath) => ipcRenderer.invoke('fs:readFile', filePath),
  writeFile: (filePath, data) => ipcRenderer.invoke('fs:writeFile', filePath, data),

  // macOS Keychain
  setKeychain: (key, val) => ipcRenderer.invoke('keychain:set', key, val),
  getKeychain: (key) => ipcRenderer.invoke('keychain:get', key),

  // Log streaming (renderer subscribes; main pushes events)
  onLog: (cb) => ipcRenderer.on('log:line', (_, line) => cb(line)),
  offLog: (cb) => ipcRenderer.removeListener('log:line', cb),
});
