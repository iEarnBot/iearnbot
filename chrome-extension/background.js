// Background Service Worker — badge updates every minute
chrome.alarms.create('refresh', { periodInMinutes: 1 })

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== 'refresh') return
  try {
    const { server_url } = await chrome.storage.local.get('server_url')
    const url = server_url || 'http://localhost:7799'
    const r = await fetch(`${url}/api/ipc`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cmd: 'get_positions', args: {} }),
      signal: AbortSignal.timeout(8000)
    })
    const d = await r.json()
    const count = d.positions?.length || 0
    chrome.action.setBadgeText({ text: count > 0 ? String(count) : '' })
    chrome.action.setBadgeBackgroundColor({ color: '#f97316' })
  } catch(e) {
    chrome.action.setBadgeText({ text: '' })
  }
})
