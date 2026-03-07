/* ── app.js — Renderer process entry ─────────────────────── */
'use strict';

// ── Page navigation ──────────────────────────────────────
const pageFrame = document.getElementById('pageFrame');
const navItems  = document.querySelectorAll('.nav-item[data-page]');

function navigateTo(page) {
  pageFrame.src = `pages/${page}.html`;
  navItems.forEach(btn => {
    btn.classList.toggle('active', btn.dataset.page === page);
  });
  localStorage.setItem('lastPage', page);
}

navItems.forEach(btn => {
  btn.addEventListener('click', () => navigateTo(btn.dataset.page));
});

// Restore last page on load
const lastPage = localStorage.getItem('lastPage') || 'markets';
navigateTo(lastPage);

// ── Status polling ───────────────────────────────────────
const botStatusPill = document.getElementById('botStatusPill');
const botStatusText = document.getElementById('botStatusText');

async function refreshStatus() {
  try {
    if (window.ipcApi) {
      const s = await window.ipcApi.pythonStatus();
      const running = s?.running ?? false;
      botStatusPill.classList.toggle('running', running);
      botStatusText.textContent = running ? 'Running' : 'Stopped';
    }
  } catch {
    // ignore
  }
}

refreshStatus();
setInterval(refreshStatus, 5000);

// ── Log forwarding to logs page ──────────────────────────
if (window.ipcApi) {
  window.ipcApi.onLog((line) => {
    // Broadcast to child iframe if it's the logs page
    try {
      if (pageFrame.contentWindow && pageFrame.src.includes('logs')) {
        pageFrame.contentWindow.postMessage({ type: 'log:line', payload: line }, '*');
      }
    } catch { /* cross-origin guard */ }
  });
}
