// Content Script — Polymarket & X page enhancement
(function() {
  'use strict'

  // ── Polymarket: inject signal overlay on market cards ──
  if (location.hostname.includes('polymarket.com')) {
    let injected = false
    const tryInject = () => {
      if (injected) return
      const cards = document.querySelectorAll('[class*="market"], [data-testid*="market"]')
      if (cards.length === 0) return
      injected = true
      cards.forEach(card => {
        if (card.querySelector('.ieb-tag')) return
        const tag = document.createElement('div')
        tag.className = 'ieb-tag'
        tag.textContent = '🔥 iEranBot'
        tag.style.cssText = [
          'position:absolute', 'top:8px', 'right:8px',
          'background:rgba(249,115,22,.85)', 'color:#fff',
          'font-size:10px', 'font-weight:700',
          'padding:2px 7px', 'border-radius:99px',
          'z-index:999', 'pointer-events:none',
          'font-family:Inter,sans-serif'
        ].join(';')
        card.style.position = 'relative'
        card.appendChild(tag)
      })
    }
    setTimeout(tryInject, 1500)
    new MutationObserver(tryInject).observe(document.body, { childList: true, subtree: true })
  }

  // ── X/Twitter: add "Generate Strategy" button on posts ──
  if (location.hostname.includes('x.com') || location.hostname.includes('twitter.com')) {
    const addStratBtn = (article) => {
      if (article.querySelector('.ieb-strat-btn')) return
      const actions = article.querySelector('[role="group"]')
      if (!actions) return
      const btn = document.createElement('button')
      btn.className = 'ieb-strat-btn'
      btn.innerHTML = '🔥'
      btn.title = 'Generate strategy with iEarn.Bot'
      btn.style.cssText = [
        'background:none', 'border:none', 'cursor:pointer',
        'font-size:16px', 'padding:4px 8px', 'border-radius:99px',
        'transition:background .2s', 'margin-left:4px'
      ].join(';')
      btn.addEventListener('click', (e) => {
        e.stopPropagation()
        const text = article.querySelector('[data-testid="tweetText"]')?.innerText || ''
        const tweetUrl = window.location.href
        chrome.runtime.sendMessage({ type: 'OPEN_STRATEGY', text, url: tweetUrl })
      })
      actions.appendChild(btn)
    }
    const scanPosts = () => document.querySelectorAll('article').forEach(addStratBtn)
    setTimeout(scanPosts, 2000)
    new MutationObserver(scanPosts).observe(document.body, { childList: true, subtree: true })
  }
})()
