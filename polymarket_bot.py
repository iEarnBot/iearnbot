#!/usr/bin/env python3
"""
Polymarket 自动交易机器人 - 完全本地运行，无需 LLM
V1 + V2-SG + V3-SG 三策略循环

运行方式：
  python3 polymarket_bot.py          # 单次执行
  python3 polymarket_bot.py --loop   # 持续循环（每30分钟一次）
  python3 polymarket_bot.py --dry    # 模拟运行不下注
"""

import argparse
import asyncio
import glob
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ── 路径配置 ──────────────────────────────────────────────
SKILL_DIR = Path.home() / '.openclaw/skills/polyclaw'
WORKSPACE = Path.home() / '.openclaw/workspace'
LB_DIR = WORKSPACE / 'polymarket_leaderboard'
ACCOUNTS_FILE = WORKSPACE / 'polymarket_v3sg_accounts.json'
FOLLOWED_FILE = WORKSPACE / 'polymarket_rename_followed.json'
LOG_FILE = WORKSPACE / 'polymarket_bot.log'
MY_ADDR = '0x2c6c1BF553A72d2d17f560FdeD8287b28659DeB8'
RENAME_ADDR = '0xf6963d4cdbb6f26d753bda303e9513132afb1b7d'

# ── 资金分配（V3-SG 优先）────────────────────────────────
# V3-SG : V2-SG : V1 = 50% : 35% : 15%
ALLOC_V3   = 0.50
ALLOC_V2   = 0.35
ALLOC_V1   = 0.15

# ── 金额档位（阶段A）──────────────────────────────────────
BET_V1 = 5.0
BET_V2 = {1: 3.0, 2: 5.0, 3: 5.0, 4: 8.0}   # 1钱包→$3, 2-3→$5, 4+→$8
BET_V3 = {40: 3.0, 60: 5.0, 80: 8.0}          # 按评分档位
MIN_BET = 2.0
MIN_BALANCE = 3.0

# ── 止盈间隔（每N次循环扫一次）──────────────────────────
TAKE_PROFIT_EVERY = 2  # 每2次心跳（约60分钟）扫一次止盈
_tp_counter = 0

# ── 工具函数 ──────────────────────────────────────────────
def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')

def fetch(url, timeout=8):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def get_balance():
    # 直接用 venv python + wallet_manager，不依赖 uv
    sys.path.insert(0, str(SKILL_DIR / 'lib'))
    sys.path.insert(0, str(SKILL_DIR / 'scripts'))
    from wallet_manager import WalletManager
    w = WalletManager()
    bal = w.get_balances()
    return float(bal.usdc_e)

def get_my_positions_full():
    """返回完整持仓列表（含eventId/conditionId），用于买入前去重"""
    try:
        return fetch(f'https://data-api.polymarket.com/positions?user={MY_ADDR}&sizeThreshold=0&limit=100')
    except:
        return []

def get_my_cids():
    positions = get_my_positions_full()
    return {p['conditionId'] for p in positions if float(p.get('currentValue') or 0) > 0.5}

def get_my_condition_ids_set():
    """返回我已持有的 conditionId 集合（用于防止对冲买入）"""
    pos = get_my_positions_full()
    # conditionId → 已持有的 outcomeIndex 列表
    held = {}
    for p in pos:
        cid = p.get('conditionId','')
        idx = p.get('outcomeIndex', -1)
        if cid and float(p.get('size',0)) > 0.05:
            held.setdefault(cid, set()).add(idx)
    return held

def get_positions(addr):
    try:
        return fetch(f'https://data-api.polymarket.com/positions?user={addr}&sizeThreshold=0&limit=50', timeout=6)
    except:
        return []

def load_evolution_params():
    """读取进化引擎生成的动态参数"""
    params_file = WORKSPACE / 'polymarket_params.json'
    if params_file.exists():
        try:
            return json.load(open(params_file))
        except: pass
    return {'disabled_market_types': [], 'boosted_market_types': [], 'min_price': 0.35}

def classify_market(title: str) -> str:
    t = title.lower()
    if 'bitcoin' in t or 'btc' in t: return 'BTC_direction'
    if 'solana' in t or 'sol' in t:  return 'SOL_direction'
    if any(x in t for x in ['cavaliers','lakers','celtics','bucks','rockets','thunder',
        'nuggets','pistons','timberwolves','76ers','clippers','pelicans','kings',
        'hawks','pacers','nets','wizards','jazz','grizzlies','spurs','heat','knicks']): return 'NBA'
    if any(x in t for x in ['blackhawks','wild','blues','flames','stars','canucks',
        'ducks','jets','sharks','panthers','hurricanes','rangers','red wings',
        'predators','kraken','golden knights','avalanche','lightning']): return 'NHL'
    if any(x in t for x in ['counter-strike','cs','esport','valorant']): return 'Esports'
    if any(x in t for x in ['real madrid','barcelona','arsenal','chelsea','bologna',
        'benfica','pisa','newcastle','manchester','milan','inter','atletico']): return 'Football_EU'
    if any(x in t for x in ['spread','over','under']): return 'Spread_OU'
    return 'Other'

def filter_positions(positions, my_cids, now, my_held_cids=None):
    """过滤出有效跟单仓位，防止对冲买入"""
    evo = load_evolution_params()
    disabled_types = set(evo.get('disabled_market_types', []))
    min_price = evo.get('min_price', 0.35)

    valid = []
    total_val = sum(float(p.get('currentValue') or 0) for p in positions)
    for p in positions:
        cid = p.get('conditionId', '')
        if cid in my_cids:
            continue

        # ── 对冲保护：如果我已经持有同一 conditionId 的另一方向，跳过 ────────
        if my_held_cids and cid in my_held_cids:
            target_idx = p.get('outcomeIndex', -1)
            held_idxs  = my_held_cids[cid]
            if target_idx not in held_idxs:  # 对方向
                log(f'  ⚠️ 跳过对冲: {p.get("title","")[:35]} {p.get("outcome","")} (已持另一方向)')
                continue

        price = float(p.get('curPrice') or 0)
        val = float(p.get('currentValue') or 0)
        if val < 2 or price > 0.88 or price < min_price:
            continue
        # 进化参数：禁用低胜率市场类型
        mtype = classify_market(p.get('title',''))
        if mtype in disabled_types:
            continue
        if total_val > 0 and val / total_val > 0.75:
            continue
        try:
            end = p.get('endDate', '').replace('Z', '+00:00')
            if 'T' not in end:
                end += 'T23:59:00+00:00'
            mins = (datetime.fromisoformat(end) - now).total_seconds() / 60
        except:
            continue
        if mins < 30 or mins > 10080:
            continue
        valid.append({
            'cid': cid, 'outcome': p.get('outcome', ''),
            'price': price, 'val': val, 'mins': mins,
            'outcomeIndex': p.get('outcomeIndex', -1),
            'eventId': p.get('eventId', ''),
            'title': p.get('title', '')[:50],
            'slug': p.get('eventSlug', '')
        })
    return valid

async def place_bet(market_id, position, amount, note, dry_run=False):
    """执行下注"""
    if dry_run:
        log(f'  [DRY] {note} → {position} ${amount:.2f}')
        return True
    log(f'  下注: {note} → {position} ${amount:.2f}')
    try:
        code = f"""
import asyncio, sys, argparse
sys.path.insert(0, 'scripts')
import trade
async def run():
    args = argparse.Namespace(market_id='{market_id}', position='{position}', amount={amount}, skip_sell=False, json=False)
    await trade.cmd_buy(args)
asyncio.run(run())
"""
        result = subprocess.run(
            ['/opt/homebrew/bin/uv', 'run', 'python', '-c', code],
            capture_output=True, text=True, cwd=SKILL_DIR, timeout=60
        )
        if 'Trade executed successfully' in result.stdout:
            log(f'  ✅ 成功')
            return True
        else:
            log(f'  ❌ 失败: {result.stdout[-200:]}')
            return False
    except Exception as e:
        log(f'  ❌ 异常: {e}')
        return False

def get_market_id(slug, target_outcome=None, position='YES'):
    """从 slug 找最优 market ID"""
    try:
        data = fetch(f'https://gamma-api.polymarket.com/events?slug={slug}', timeout=6)
        best_id = None; best_liq = 0; best_price = 0
        for e in (data if isinstance(data, list) else []):
            for m in e.get('markets', []):
                prices = m.get('outcomePrices', '[]')
                if isinstance(prices, str): prices = json.loads(prices)
                outcomes = m.get('outcomes', '[]')
                if isinstance(outcomes, str): outcomes = json.loads(outcomes)
                liq = float(m.get('liquidityNum') or 0)
                if not prices or liq < 15000: continue  # 流动性>$15K才CLOB成功率高
                # 找匹配 outcome 的价格
                if target_outcome:
                    match = [i for i, o in enumerate(outcomes) if target_outcome.lower() in o.lower()]
                    if not match: continue
                    idx = match[0]
                    p = float(prices[idx])
                else:
                    p = float(prices[1]) if position == 'NO' else float(prices[0])
                if p < 0.10 or p > 0.92: continue
                if liq > best_liq:
                    best_liq = liq; best_id = m['id']; best_price = p
        return str(best_id) if best_id else None, best_price
    except:
        return None, 0

# ── Step 0: 存档今日榜单 ─────────────────────────────────
def archive_leaderboard():
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    out_path = LB_DIR / f'{today}.json'
    if out_path.exists():
        return
    LB_DIR.mkdir(exist_ok=True)
    try:
        req = urllib.request.Request(
            'https://polymarket.com/zh/leaderboard',
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'})
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode()
        chunks = re.findall(
            r'"rank":(\d+),"proxyWallet":"(0x[^"]+)","name":"([^"]*)","pseudonym":"([^"]*)","amount":([\d\.]+),"pnl":([\-\d\.]+),"volume":([\d\.]+)',
            html)
        seen = set(); records = []
        now_str = datetime.now(timezone.utc).isoformat()
        for rank, addr, name, pseudo, amt, pnl, vol in chunks:
            if addr not in seen:
                seen.add(addr)
                records.append({'rank': int(rank), 'address': addr,
                    'name': name or pseudo or addr[:12],
                    'pnl': float(pnl), 'volume': float(vol),
                    'date': today, 'timestamp': now_str})
        records.sort(key=lambda x: x['pnl'], reverse=True)
        with open(out_path, 'w') as f:
            json.dump(records, f, indent=2)
        log(f'Step0: 存档榜单 {today} ({len(records)}条)')
    except Exception as e:
        log(f'Step0: 存档失败 {e}')

# ── Step 1: V1 BTC/ETH 看涨 ──────────────────────────────
async def run_v1(balance, my_cids, dry_run):
    log('--- V1: BTC/ETH 看涨 ---')
    try:
        btc = float(fetch('https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT', timeout=5)['price'])
        btc_1h = float(fetch('https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=2', timeout=5)[0][4])
        trend = 'UP' if btc > btc_1h else 'DOWN'
        log(f'  BTC: ${btc:,.0f} 1h前: ${btc_1h:,.0f} 趋势: {trend}')
        if trend == 'DOWN':
            log('  BTC下跌趋势，跳过V1')
            return 0
    except Exception as e:
        log(f'  价格获取失败: {e}，跳过V1')
        return 0

    # 找当前 hourly 市场
    now = datetime.now(timezone.utc)
    hour = now.hour
    ampm = 'am' if hour < 12 else 'pm'
    h12 = hour % 12 or 12
    month_name = now.strftime('%B').lower()
    day = now.day
    slug = f'bitcoin-up-or-down-{month_name}-{day}-{h12}{ampm}-et'
    market_id, price = get_market_id(slug, 'Up', 'YES')
    if not market_id or price < 0.52:
        log(f'  未找到合适 hourly 市场 (slug:{slug})')
        return 0

    amt = min(BET_V1, balance * 0.33)
    if amt < MIN_BET:
        log(f'  余额不足 V1')
        return 0
    await place_bet(market_id, 'YES', amt, f'BTC {h12}{ampm} ET UP ${price:.2f}', dry_run)
    return amt

def price_adjusted_bet(base_amt, price, market_type=''):
    """按入场价 + 进化参数调整下注金额"""
    evo = load_evolution_params()
    boosted = set(evo.get('boosted_market_types', []))
    # 基础调整
    if price < 0.45:
        amt = min(base_amt, 3.0)
    elif price >= 0.65:
        amt = min(base_amt * 1.5, 12.0)
    else:
        amt = base_amt
    # 高胜率市场加码 20%
    if market_type in boosted:
        amt = min(amt * 1.2, 15.0)
    return amt

def dedup_by_event(signals_dict, my_event_ids):
    """同一 eventId 只保留市值最大的方向，避免双向持仓"""
    result = []
    seen_events = set(my_event_ids)
    for sigs in signals_dict:
        eid = sigs[0].get('eventId', '')
        if eid and eid in seen_events:
            continue
        if eid:
            seen_events.add(eid)
        result.append(sigs)
    return result

# ── Step 2: V2-SG 今日榜单跟单 ────────────────────────────
async def run_v2sg(balance, my_cids, dry_run):
    log('--- V2-SG: 今日榜单跟单 ---')
    now = datetime.now(timezone.utc)
    try:
        req = urllib.request.Request('https://polymarket.com/zh/leaderboard',
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'})
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode()
        chunks = re.findall(
            r'"proxyWallet":"(0x[^"]+)","name":"([^"]*)","pseudonym":"([^"]*)","amount":[\d\.]+,"pnl":([\-\d\.]+)',
            html)
        seen = set(); addrs = []
        for addr, name, pseudo, pnl in chunks:
            if addr not in seen and float(pnl) > 0:
                seen.add(addr); addrs.append((addr, name or pseudo))
        addrs = addrs[:15]
    except Exception as e:
        log(f'  榜单获取失败: {e}')
        return 0

    # 获取我已有的 eventId 和 conditionId（双重防对冲）
    my_positions = get_my_positions_full()
    my_event_ids = {p.get('eventId','') for p in my_positions if p.get('eventId')}
    my_held_cids = get_my_condition_ids_set()

    signals = defaultdict(list)
    for addr, name in addrs:
        for pos in filter_positions(get_positions(addr), my_cids, now, my_held_cids):
            signals[pos['cid']].append({**pos, 'wallet': name})

    ranked = sorted(signals.values(), key=lambda s: (-len(s), s[0]['mins'], -sum(x['val'] for x in s)))
    ranked = dedup_by_event(ranked, my_event_ids)  # 去掉已持对立方向
    total_spent = 0
    budget = balance * ALLOC_V2

    for sigs in ranked:
        if budget - total_spent < MIN_BET:
            break
        n = len(sigs)
        base_amt = BET_V2.get(min(n, 4), 8.0)
        amt = price_adjusted_bet(base_amt, sigs[0]['price'])
        amt = min(amt, budget - total_spent)
        if amt < MIN_BET:
            break
        sig = sigs[0]
        market_id, price = get_market_id(sig['slug'], sig['outcome'])
        if not market_id:
            continue
        pos = 'YES' if sig['outcome'].lower() not in ['no','down','under'] else 'NO'
        note = f"V2[{n}w] {sig['outcome']} ${sig['price']:.2f} {sig['mins']/60:.1f}h | {sig['title'][:30]}"
        ok = await place_bet(market_id, pos, amt, note, dry_run)
        if ok:
            total_spent += amt
            my_cids.add(sig['cid'])

    log(f'  V2-SG 共下注 ${total_spent:.2f}')
    return total_spent

# ── Step 3: V3-SG rename 实时跟单 ─────────────────────────
async def run_v3_rename(balance, my_cids, dry_run):
    now = datetime.now(timezone.utc)
    # 只在 14:00-21:00 UTC 活跃
    if not (14 <= now.hour < 21):
        return 0
    log('--- V3-SG: rename 实时跟单 ---')

    # 读取已跟记录
    followed = set()
    if FOLLOWED_FILE.exists():
        followed = set(json.load(open(FOLLOWED_FILE)))

    try:
        trades = fetch(f'https://data-api.polymarket.com/trades?user={RENAME_ADDR}&limit=20', timeout=6)
    except:
        return 0

    total_spent = 0
    for t in trades:
        if time.time() - t.get('timestamp', 0) > 300:
            continue
        cid = t.get('conditionId', '')
        if cid in followed or cid in my_cids:
            continue
        slug = t.get('eventSlug', '')
        if 'updown-15m' not in slug and 'updown-5m' not in slug:
            continue
        # 检查结算时间
        market_id, price = get_market_id(slug)
        if not market_id or price < 0.35 or price > 0.88:
            continue
        outcome = t.get('outcome', '')
        pos = 'YES' if outcome.lower() in ['up','yes'] else 'NO'
        amt = min(3.0, balance * 0.33 - total_spent)
        if amt < MIN_BET:
            break
        note = f'V3-rename {outcome} ${price:.2f} | {t.get("title","")[:30]}'
        ok = await place_bet(market_id, pos, amt, note, dry_run)
        if ok:
            total_spent += amt
            followed.add(cid)
            my_cids.add(cid)

    with open(FOLLOWED_FILE, 'w') as f:
        json.dump(list(followed), f)
    return total_spent

# ── Step 4: V3-SG 名单账号跟单 ────────────────────────────
async def run_v3_accounts(balance, my_cids, v2_addrs, dry_run):
    log('--- V3-SG: 名单账号跟单 ---')
    now = datetime.now(timezone.utc)
    if not ACCOUNTS_FILE.exists():
        return 0

    accounts = json.load(open(ACCOUNTS_FILE))
    v2_set = set(v2_addrs)
    signals = defaultdict(list)

    for acct in accounts:
        if not acct.get('active') or acct['addr'] in v2_set:
            continue
        my_held_cids = get_my_condition_ids_set()
        for pos in filter_positions(get_positions(acct['addr']), my_cids, now, my_held_cids):
            signals[pos['cid']].append({**pos, 'wallet': acct['name'], 'score': acct['score'],
                'src_addr': acct['addr'], 'src_time': int(time.time())})

    ranked = sorted(signals.values(), key=lambda s: (-len(s), s[0]['mins'], -max(x['score'] for x in s)))

    # 去掉已持有对立方向的 event
    my_positions = get_my_positions_full()
    my_event_ids = {p.get('eventId','') for p in my_positions if p.get('eventId')}
    ranked = dedup_by_event(ranked, my_event_ids)

    total_spent = 0
    budget = balance * ALLOC_V3

    for sigs in ranked:
        if budget - total_spent < MIN_BET:
            break
        max_score = max(s['score'] for s in sigs)
        base_amt = BET_V3[40] if max_score < 60 else (BET_V3[60] if max_score < 80 else BET_V3[80])
        # 按入场价调整
        amt = price_adjusted_bet(base_amt, sigs[0]['price'])
        if len(sigs) > 1:
            amt = min(amt * 1.2, 10.0)
        amt = min(amt, budget - total_spent)
        if amt < MIN_BET:
            break
        sig = sigs[0]
        market_id, price = get_market_id(sig['slug'], sig['outcome'])
        if not market_id:
            continue
        pos = 'YES' if sig['outcome'].lower() not in ['no','down','under'] else 'NO'
        note = f"V3[{max_score}分] {sig['outcome']} ${sig['price']:.2f} | {sig['title'][:28]}"
        ok = await place_bet(market_id, pos, amt, note, dry_run)
        if ok:
            total_spent += amt
            my_cids.add(sig['cid'])

    log(f'  V3-SG 共下注 ${total_spent:.2f}')
    return total_spent

# ── 主循环 ────────────────────────────────────────────────
async def run_once(dry_run=False, mode='full'):
    """
    mode:
      'fast'  - 每5分钟: 止盈 + rename高频
      'mid'   - 每15分钟: V2-SG + V3-SG
      'v1'    - 整点后5分钟: V1 BTC hourly
      'full'  - 全量（向后兼容）
    """
    global _tp_counter
    log('=' * 50)
    log(f'Polymarket Bot [{mode}] 开始执行')

    # Step 0: 存档榜单
    archive_leaderboard()

    # Step 0b: 自动兑换 USDC native → USDC.e（如有）
    try:
        from usdc_swap import swap_usdc_to_usdce
        swap_usdc_to_usdce(dry_run=dry_run)
    except Exception as e:
        log(f'USDC swap 检测异常: {e}')

    # Step 1: 止盈扫描（fast/full 模式每次都跑）
    if mode in ('fast', 'full'):
        try:
            from polymarket_take_profit import run_take_profit
            sold = await run_take_profit(dry_run=dry_run)
            if sold > 0:
                log(f'止盈卖出 {sold} 笔，等待余额更新...')
                if not dry_run:
                    import time as t; t.sleep(5)
        except Exception as e:
            log(f'止盈模块异常: {e}')

    # Step 2: 余额检查（非 fast 模式才做交易）
    if mode == 'fast':
        # fast 模式只做 rename 高频跟单
        try:
            my_cids = get_my_cids()
            balance = get_balance()
            if balance >= MIN_BALANCE:
                spent = await run_v3_rename(balance, my_cids, dry_run)
                log(f'[fast] rename=${spent:.2f}')
        except Exception as e:
            log(f'[fast] 异常: {e}')
        log('执行完毕')
        return

    # Step 3: 余额 & 持仓（mid/v1/full）
    try:
        balance = get_balance()
        log(f'余额: ${balance:.2f} USDC.e')
    except Exception as e:
        log(f'余额获取失败: {e}')
        return

    if balance < MIN_BALANCE:
        log(f'余额不足 ${MIN_BALANCE}，等待结算回款')
        return

    try:
        my_cids = get_my_cids()
        log(f'已持有: {len(my_cids)} 个市场')
    except Exception as e:
        log(f'持仓获取失败: {e}')
        my_cids = set()

    if mode == 'v1':
        # 只跑 V1 BTC hourly
        spent = await run_v1(balance, my_cids, dry_run)
        log(f'[v1] V1=${spent:.2f}')
        log('执行完毕')
        return

    # mid / full：跑 V2-SG + V3-SG
    try:
        req = urllib.request.Request('https://polymarket.com/zh/leaderboard',
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'})
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode()
        chunks = re.findall(r'"proxyWallet":"(0x[^"]+)"', html)
        v2_addrs = list(dict.fromkeys(chunks))[:15]
    except:
        v2_addrs = []

    # rename 高频（mid/full 也跑）
    spent_rename = await run_v3_rename(balance, my_cids, dry_run)
    # V3-SG 50%
    spent_v3 = await run_v3_accounts(balance - spent_rename, my_cids, v2_addrs, dry_run)
    # V2-SG 35%
    spent_v2 = await run_v2sg(balance - spent_rename - spent_v3, my_cids, dry_run)

    if mode == 'full':
        # full 模式额外跑 V1
        spent_v1 = await run_v1(balance - spent_rename - spent_v3 - spent_v2, my_cids, dry_run)
    else:
        spent_v1 = 0

    total = spent_v1 + spent_v2 + spent_rename + spent_v3
    log(f'本轮: rename=${spent_rename:.2f} V3=${spent_v3:.2f} V2=${spent_v2:.2f} V1=${spent_v1:.2f} 共=${total:.2f}')

    # 每次 mid/full 跑完后触发进化分析
    if mode in ('mid', 'full'):
        try:
            from polymarket_evolution import analyze_and_evolve
            params, changes = analyze_and_evolve()
            if changes:
                log(f'[进化] 策略自动调整: {len(changes)}项')
                for c in changes:
                    log(f'[进化]   → {c}')
        except Exception as e:
            log(f'[进化] 分析异常: {e}')

    log('执行完毕')

def main():
    parser = argparse.ArgumentParser(description='Polymarket 自动交易机器人')
    parser.add_argument('--loop', action='store_true', help='持续循环运行')
    parser.add_argument('--dry', action='store_true', help='模拟运行，不实际下注')
    parser.add_argument('--mode', default='full', choices=['fast','mid','v1','full'],
                        help='运行模式: fast=5min止盈+高频 mid=15min跟单 v1=整点BTC full=全量')
    parser.add_argument('--interval', type=int, default=None,
                        help='循环间隔秒数（不指定则按mode自动选择）')
    args = parser.parse_args()

    # 按 mode 设默认间隔
    default_intervals = {'fast': 300, 'mid': 900, 'v1': 3600, 'full': 1800}
    interval = args.interval or default_intervals[args.mode]

    if args.loop:
        log(f'循环模式 [{args.mode}] 启动，间隔 {interval}秒')
        while True:
            try:
                asyncio.run(run_once(args.dry, args.mode))
            except Exception as e:
                log(f'执行异常: {e}')
            log(f'等待 {interval}秒...')
            time.sleep(interval)
    else:
        asyncio.run(run_once(args.dry, args.mode))

if __name__ == '__main__':
    main()
