#!/usr/bin/env python3
"""
Polymarket 自我进化引擎
每次运行后分析盈亏，自动更新策略参数
无需 LLM，纯本地规则进化
"""

import json
import os
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE   = Path.home() / '.openclaw/workspace'
BOT_FILE    = WORKSPACE / 'polymarket_bot.py'
LOG_FILE    = WORKSPACE / 'polymarket_bot.log'
STATS_FILE  = WORKSPACE / 'polymarket_stats.json'
REPORT_FILE = WORKSPACE / 'polymarket_evolution_report.md'

MY_ADDR = '0x2c6c1BF553A72d2d17f560FdeD8287b28659DeB8'

def fetch(url):
    r = urllib.request.urlopen(urllib.request.Request(
        url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=10)
    return json.loads(r.read())

def load_stats():
    if STATS_FILE.exists():
        return json.load(open(STATS_FILE))
    return {
        'settled_bets': [],        # 已结算的每笔记录
        'strategy_stats': {},      # 策略维度统计
        'price_range_stats': {},   # 价格区间胜率
        'market_type_stats': {},   # 市场类型胜率
        'clob_stats': {'success': 0, 'fail': 0},
        'params_history': [],      # 参数变更记录
        'last_run': None,
    }

def save_stats(stats):
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=2, default=str)

def classify_market(title: str) -> str:
    t = title.lower()
    if 'bitcoin' in t or 'btc' in t: return 'BTC_direction'
    if 'solana' in t or 'sol' in t:  return 'SOL_direction'
    if any(x in t for x in ['nba','cavaliers','lakers','celtics','bucks','rockets',
                              'thunder','nuggets','pistons','timberwolves','76ers',
                              'clippers','pelicans','kings','hawks','pacers','nets',
                              'wizards','jazz','grizzlies','spurs','heat','knicks']): return 'NBA'
    if any(x in t for x in ['nhl','blackhawks','wild','blues','flames','stars',
                              'canucks','ducks','jets','sharks','panthers','hurricanes',
                              'rangers','red wings','predators','kraken','golden knights',
                              'avalanche','lightning','bruins','penguins']): return 'NHL'
    if any(x in t for x in ['counter-strike','cs','esport','valorant']): return 'Esports'
    if any(x in t for x in ['real madrid','barcelona','arsenal','chelsea','bologna',
                              'benfica','pisa','newcastle','manchester','milan','inter',
                              'juventus','atletico','bundesliga','laliga','premier']): return 'Football_EU'
    if any(x in t for x in ['spread','over','under','total']): return 'Spread_OU'
    return 'Other'

def price_bucket(price: float) -> str:
    if price < 0.35: return '<0.35'
    if price < 0.50: return '0.35-0.50'
    if price < 0.65: return '0.50-0.65'
    if price < 0.80: return '0.65-0.80'
    return '0.80-0.90'

def analyze_and_evolve():
    now = datetime.now(timezone.utc)
    stats = load_stats()

    # ── 1. 获取所有持仓，识别新结算的 ──
    positions = fetch(f'https://data-api.polymarket.com/positions?user={MY_ADDR}&sizeThreshold=0&limit=100')
    activity  = fetch(f'https://data-api.polymarket.com/activity?user={MY_ADDR}&limit=500')

    splits = {t['conditionId']: t for t in activity if t.get('type') == 'SPLIT'}
    sells  = [t for t in activity if t.get('type') == 'TRADE' and t.get('side') == 'SELL']

    # CLOB 统计
    clob_ok   = len([s for s in sells if s.get('timestamp',0) - splits.get(s.get('conditionId',''), {}).get('timestamp',0) <= 300 and float(s.get('usdcSize') or 0) > 0.1])
    clob_fail = len([c for c in splits.values()]) - clob_ok
    stats['clob_stats'] = {'success': clob_ok, 'fail': max(0, clob_fail), 'rate': round(clob_ok/max(clob_ok+clob_fail,1), 3)}

    # ── 2. 扫描已结算仓位，更新统计 ──
    known_cids = {b['cid'] for b in stats['settled_bets']}
    new_settled = []

    for p in positions:
        cid   = p.get('conditionId', '')
        price = float(p.get('curPrice') or 0)
        size  = float(p.get('size') or 0)
        if size < 0.1: continue

        try:
            end  = p.get('endDate','').replace('Z','+00:00')
            if 'T' not in end: end += 'T23:59:00+00:00'
            mins = (datetime.fromisoformat(end) - now).total_seconds() / 60
        except: continue

        if mins >= 0 or cid in known_cids:
            continue

        # 找对应 SPLIT 获得入场价
        sp = splits.get(cid, {})
        entry_price = float(sp.get('price') or p.get('avgPrice') or 0.5)
        market_type = classify_market(p.get('title',''))
        bucket = price_bucket(entry_price)

        won = price > 0.90
        lost = price < 0.10
        if not won and not lost:
            continue  # 还没最终结算

        record = {
            'cid': cid,
            'title': p.get('title','')[:50],
            'outcome': p.get('outcome',''),
            'entry_price': round(entry_price, 3),
            'result_price': round(price, 3),
            'size': size,
            'won': won,
            'pnl': round(size - float(sp.get('usdcSize') or size), 2),
            'market_type': market_type,
            'price_bucket': bucket,
            'settled_at': now.isoformat(),
        }
        stats['settled_bets'].append(record)
        new_settled.append(record)
        known_cids.add(cid)

    # ── 3. 计算各维度胜率 ──
    all_bets = stats['settled_bets']

    # 按市场类型
    mtype_stats = defaultdict(lambda: {'win': 0, 'lose': 0, 'pnl': 0})
    for b in all_bets:
        mt = b['market_type']
        mtype_stats[mt]['win' if b['won'] else 'lose'] += 1
        mtype_stats[mt]['pnl'] += b.get('pnl', 0)

    # 按价格区间
    bucket_stats = defaultdict(lambda: {'win': 0, 'lose': 0})
    for b in all_bets:
        bucket_stats[b['price_bucket']]['win' if b['won'] else 'lose'] += 1

    stats['market_type_stats'] = {k: dict(v) for k, v in mtype_stats.items()}
    stats['price_range_stats'] = {k: dict(v) for k, v in bucket_stats.items()}
    stats['last_run'] = now.isoformat()

    # ── 4. 自动进化决策 ──
    changes = []
    current_params = _read_current_params()

    for mt, s in mtype_stats.items():
        total = s['win'] + s['lose']
        if total < 3: continue  # 样本不足
        wr = s['win'] / total
        if wr < 0.35 and total >= 5:
            changes.append({
                'type': 'DISABLE_MARKET_TYPE',
                'market_type': mt,
                'win_rate': round(wr, 2),
                'sample': total,
                'action': f'市场类型 [{mt}] 胜率{wr*100:.0f}% < 35%，跳过此类市场'
            })
        elif wr > 0.70 and total >= 5:
            changes.append({
                'type': 'BOOST_MARKET_TYPE',
                'market_type': mt,
                'win_rate': round(wr, 2),
                'sample': total,
                'action': f'市场类型 [{mt}] 胜率{wr*100:.0f}% > 70%，加大投注'
            })

    for bkt, s in bucket_stats.items():
        total = s['win'] + s['lose']
        if total < 3: continue
        wr = s['win'] / total
        if wr < 0.35 and total >= 5:
            changes.append({
                'type': 'DISABLE_PRICE_BUCKET',
                'bucket': bkt,
                'win_rate': round(wr, 2),
                'sample': total,
                'action': f'价格区间 [{bkt}] 胜率{wr*100:.0f}% < 35%，提高最低入场价'
            })

    # ── 5. 应用参数变更 ──
    applied = []
    disabled_types = set(current_params.get('disabled_market_types', []))
    boosted_types  = set(current_params.get('boosted_market_types', []))
    min_price = current_params.get('min_price', 0.35)

    for c in changes:
        if c['type'] == 'DISABLE_MARKET_TYPE':
            if c['market_type'] not in disabled_types:
                disabled_types.add(c['market_type'])
                applied.append(c['action'])
        elif c['type'] == 'BOOST_MARKET_TYPE':
            if c['market_type'] not in boosted_types:
                boosted_types.add(c['market_type'])
                applied.append(c['action'])
        elif c['type'] == 'DISABLE_PRICE_BUCKET':
            # 提高最低价格门槛
            bucket_min = float(c['bucket'].split('-')[0].replace('<','0'))
            if bucket_min + 0.05 > min_price:
                min_price = round(bucket_min + 0.05, 2)
                applied.append(c['action'])

    new_params = {
        'disabled_market_types': list(disabled_types),
        'boosted_market_types': list(boosted_types),
        'min_price': min_price,
        'updated_at': now.isoformat(),
    }

    if applied:
        _write_params(new_params)
        stats['params_history'].append({
            'timestamp': now.isoformat(),
            'changes': applied,
            'params': new_params,
        })

    save_stats(stats)

    # ── 6. 生成进化报告 ──
    total_bets = len(all_bets)
    total_won  = sum(1 for b in all_bets if b['won'])
    overall_wr = total_won / total_bets * 100 if total_bets > 0 else 0

    report = f"""# Polymarket 策略进化报告
更新时间: {now.strftime('%Y-%m-%d %H:%M UTC')}

## 总体战绩
- 已结算: {total_bets}笔  胜率: {overall_wr:.1f}%  ({total_won}胜/{total_bets-total_won}负)
- CLOB成功率: {stats['clob_stats'].get('rate',0)*100:.0f}%

## 各市场类型胜率
| 类型 | 胜 | 负 | 胜率 | PnL |
|------|----|----|------|-----|
"""
    for mt, s in sorted(mtype_stats.items(), key=lambda x: -(x[1]['win']/(x[1]['win']+x[1]['lose']) if x[1]['win']+x[1]['lose']>0 else 0)):
        t = s['win'] + s['lose']
        wr = s['win']/t*100 if t > 0 else 0
        flag = '✅' if wr >= 60 else ('⚠️' if wr >= 40 else '❌')
        report += f"| {flag} {mt} | {s['win']} | {s['lose']} | {wr:.0f}% | ${s['pnl']:.2f} |\n"

    report += f"""
## 价格区间胜率
| 区间 | 胜 | 负 | 胜率 |
|------|----|----|------|
"""
    for bkt in ['<0.35','0.35-0.50','0.50-0.65','0.65-0.80','0.80-0.90']:
        s = bucket_stats.get(bkt, {'win':0,'lose':0})
        t = s['win'] + s['lose']
        wr = s['win']/t*100 if t > 0 else 0
        flag = '✅' if wr >= 60 else ('⚠️' if wr >= 40 else '❌')
        report += f"| {flag} {bkt} | {s['win']} | {s['lose']} | {wr:.0f}% |\n"

    report += f"""
## 当前策略参数
- 最低入场价: {new_params['min_price']}
- 禁用市场类型: {', '.join(disabled_types) or '无'}
- 加码市场类型: {', '.join(boosted_types) or '无'}

## 本次进化动作
"""
    if applied:
        for a in applied:
            report += f"- {a}\n"
    else:
        report += "- 无变更（样本不足或表现正常）\n"

    if new_settled:
        report += f"\n## 本次新增结算 ({len(new_settled)}笔)\n"
        for b in new_settled:
            icon = '✅' if b['won'] else '❌'
            report += f"- {icon} {b['outcome']} @{b['entry_price']} [{b['market_type']}] | {b['title']}\n"

    with open(REPORT_FILE, 'w') as f:
        f.write(report)

    print(report)
    return new_params, applied

def _read_current_params():
    params_file = WORKSPACE / 'polymarket_params.json'
    if params_file.exists():
        return json.load(open(params_file))
    return {'disabled_market_types': [], 'boosted_market_types': [], 'min_price': 0.35}

def _write_params(params):
    params_file = WORKSPACE / 'polymarket_params.json'
    with open(params_file, 'w') as f:
        json.dump(params, f, indent=2)
    print(f'[进化] 参数已更新: {params_file}')

if __name__ == '__main__':
    analyze_and_evolve()
