#!/usr/bin/env python3
"""
V3 跟单明细追踪：对比目标账号当前持仓 vs 我们的跟单情况
生成 polymarket_v3_trace.json 供仪表盘展示
字段说明：
  src_price  = 目标账号的 avgPrice（他的入场成本）
  my_price   = 我们的 avgPrice
  price_diff = my_price - src_price（正=我买贵了，负=我买便宜了）
  cur_price  = 现在市场价（用于判断跑赢/跑输）
"""
import json, time, urllib.request, pathlib
from datetime import datetime, timezone

WORKSPACE     = pathlib.Path.home() / '.openclaw/workspace'
ACCOUNTS_FILE = WORKSPACE / 'polymarket_v3sg_accounts.json'
TRACE_FILE    = WORKSPACE / 'polymarket_v3_trace.json'
MY_ADDR       = '0x2c6c1BF553A72d2d17f560FdeD8287b28659DeB8'

def fetch(url, ttl=60, _cache={}, _ts={}):
    now = time.time()
    if url in _cache and now - _ts.get(url,0) < ttl: return _cache[url]
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'}), timeout=9)
        d = json.loads(r.read()); _cache[url]=d; _ts[url]=now; return d
    except: return _cache.get(url, [])

def get_positions(addr):
    return fetch(f'https://data-api.polymarket.com/positions?user={addr}&sizeThreshold=0&limit=100', ttl=120)

def get_activity(addr, limit=200):
    return fetch(f'https://data-api.polymarket.com/activity?user={addr}&limit={limit}', ttl=120)

def build_trace():
    if not ACCOUNTS_FILE.exists():
        return []

    accounts  = [a for a in json.load(open(ACCOUNTS_FILE)) if a.get('active')]
    my_pos    = get_positions(MY_ADDR)
    my_act    = get_activity(MY_ADDR, 300)

    # 我的持仓 cid → 字段
    my_pos_map = {p['conditionId']: p for p in my_pos if p.get('conditionId')}

    # 我的 activity：cid → 最早 SPLIT 时间（入场时间）
    my_entry_ts = {}
    for t in my_act:
        if t.get('type') == 'SPLIT' and t.get('conditionId'):
            cid = t['conditionId']
            ts  = t.get('timestamp', 0)
            if cid not in my_entry_ts or ts < my_entry_ts[cid]:
                my_entry_ts[cid] = ts

    # 我的出场：cid → 总回收金额
    my_exit_map = {}
    for t in my_act:
        if t.get('type') in ('REDEEM','TRADE') and t.get('conditionId'):
            cid  = t['conditionId']
            usdc = float(t.get('usdcSize') or 0)
            my_exit_map[cid] = my_exit_map.get(cid, 0) + usdc

    traces = []
    seen   = set()

    for acct in accounts:
        src_positions = get_positions(acct['addr'])
        src_pos_map   = {p['conditionId']: p for p in src_positions if p.get('conditionId')}

        # 找共同持仓（目标账号现在持有，我们也持有过或正持有）
        common_cids = set(src_pos_map.keys()) & (set(my_pos_map.keys()) | set(my_entry_ts.keys()))

        for cid in common_cids:
            if cid in seen: continue  # 多账号共同持有时只记一次
            seen.add(cid)

            sp   = src_pos_map[cid]
            mp   = my_pos_map.get(cid)

            src_avg_price = float(sp.get('avgPrice') or 0)
            src_cur_price = float(sp.get('curPrice') or 0)
            src_size      = float(sp.get('size') or 0)
            src_cur_val   = float(sp.get('currentValue') or 0)
            src_pnl       = float(sp.get('cashPnl') or 0)
            src_pnl_pct   = float(sp.get('percentPnl') or 0)

            my_avg_price = float(mp.get('avgPrice') or 0) if mp else 0
            my_cur_price = float(mp.get('curPrice') or 0) if mp else 0
            my_size      = float(mp.get('size') or 0) if mp else 0
            my_cur_val   = float(mp.get('currentValue') or 0) if mp else 0
            my_cost      = float(mp.get('initialValue') or (my_size * my_avg_price)) if mp else 0
            my_total_out = my_exit_map.get(cid, 0)
            my_pnl       = (my_total_out - my_cost) if my_total_out > 0 else (my_cur_val - my_cost)
            my_entry_time = my_entry_ts.get(cid, 0)

            price_diff   = round(my_avg_price - src_avg_price, 3) if my_avg_price and src_avg_price else None
            lag_min      = None  # 无法知道src入场时间（positions不含时间戳）

            status = 'closed' if my_total_out > 0 and not mp else ('open' if mp else 'no_position')

            traces.append({
                'cid':          cid,
                'title':        sp.get('title','')[:46],
                'icon':         sp.get('icon',''),
                'outcome':      sp.get('outcome',''),
                'end_date':     sp.get('endDate',''),
                # 跟单来源
                'account':      acct['name'],
                'score':        acct.get('score', 0),
                # 目标账号当前
                'src_avg':      round(src_avg_price, 3),
                'src_cur':      round(src_cur_price, 3),
                'src_size':     round(src_size, 2),
                'src_val':      round(src_cur_val, 2),
                'src_pnl':      round(src_pnl, 2),
                'src_pnl_pct':  round(src_pnl_pct, 1),
                # 我们
                'my_entry_ts':  my_entry_time,
                'my_avg':       round(my_avg_price, 3),
                'my_cur':       round(my_cur_price, 3),
                'my_size':      round(my_size, 2),
                'my_val':       round(my_cur_val, 2),
                'my_cost':      round(my_cost, 2),
                'my_out':       round(my_total_out, 2),
                'my_pnl':       round(my_pnl, 2),
                # 对比
                'price_diff':   price_diff,   # 正=买贵了，负=买便宜了
                'status':       status,        # open / closed / no_position
                'ahead':        (src_cur_price > my_cur_price) if (src_cur_price and my_cur_price) else None,
            })

    traces.sort(key=lambda x: -x.get('my_entry_ts', 0))
    json.dump(traces, open(TRACE_FILE,'w'), indent=2, ensure_ascii=False)
    print(f'✅ V3 追踪：{len(traces)} 条  → {TRACE_FILE}')
    return traces

if __name__ == '__main__':
    build_trace()
