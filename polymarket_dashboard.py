#!/usr/bin/env python3
"""iEarn.Bot Dashboard v0.1 — http://localhost:7799"""
import json, os, subprocess, time, urllib.request, urllib.parse, pathlib, re
import concurrent.futures, threading
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from collections import defaultdict

PORT     = 7799
MY_ADDR  = '0x2c6c1BF553A72d2d17f560FdeD8287b28659DeB8'
POLYCLAW = pathlib.Path.home() / '.openclaw/skills/polyclaw'
WS       = pathlib.Path.home() / '.openclaw/workspace'
PARAMS_F = WS / 'polymarket_params.json'
STATS_F  = WS / 'polymarket_stats.json'
LOG_F    = WS / 'polymarket_bot.log'
STOP_F   = WS / 'polymarket_stop.flag'
REVIEW_F = WS / 'polymarket_review.json'
TRACE_F  = WS / 'polymarket_v3_trace.json'
V3ACC_F  = WS / 'polymarket_v3sg_accounts.json'
STRATS_F = WS / 'polymarket_strategies.json'
TP_F     = WS / 'polymarket_tp_config.json'

_cache = {}; _cache_ts = {}
_bal_cache = [0.0, 0.0]

# ─── 网络 ──────────────────────────────────────────────────────────────────────
def fetch(url, ttl=25):
    now = time.time()
    if url in _cache and now - _cache_ts.get(url, 0) < ttl: return _cache[url]
    try:
        req  = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        data = json.loads(urllib.request.urlopen(req, timeout=9).read())
        _cache[url] = data; _cache_ts[url] = now; return data
    except: return _cache.get(url, [])

def get_balance():
    now = time.time()
    if now - _bal_cache[1] < 60: return _bal_cache[0]
    try:
        env = {}
        ef = POLYCLAW / '.env'
        if ef.exists():
            for line in ef.read_text().splitlines():
                if '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1); env[k.strip()] = v.strip()
        pk  = os.environ.get('POLYCLAW_PRIVATE_KEY') or env.get('POLYCLAW_PRIVATE_KEY', '')
        rpc = os.environ.get('CHAINSTACK_NODE') or env.get('CHAINSTACK_NODE', '')
        if not pk or not rpc: return _bal_cache[0]
        from web3 import Web3; from eth_account import Account
        w3   = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 5}))
        addr = Account.from_key(pk).address
        USDC_E = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
        abi = [{"inputs":[{"name":"account","type":"address"}],"name":"balanceOf",
                "outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]
        bal = w3.eth.contract(address=w3.to_checksum_address(USDC_E), abi=abi).functions.balanceOf(addr).call() / 1e6
        _bal_cache[0] = bal; _bal_cache[1] = now; return bal
    except: return _bal_cache[0]

def get_jobs():
    try:
        r = subprocess.run(['launchctl','list'], capture_output=True, text=True, timeout=5)
        j = {}
        for nm in ['fast','mid','v1']:
            for ln in r.stdout.splitlines():
                if f'com.polymarket.{nm}' in ln:
                    pts = ln.split(); j[nm] = {'run': pts[0]!='-', 'pid': pts[0], 'exit': pts[1]}
        return j
    except: return {}

# ─── 持久化 ────────────────────────────────────────────────────────────────────
def load_params():
    if PARAMS_F.exists():
        try: return json.load(open(PARAMS_F))
        except: pass
    return {'v1_enabled':True,'v2_enabled':True,'v3_enabled':True,'fast_enabled':True,
            'bet_v1':5.0,'bet_v2_base':5.0,'bet_v3_base':5.0,
            'min_price':0.40,'max_price':0.88,'min_liquidity':20000,
            'disabled_market_types':['Football','Other'],'boosted_market_types':[]}
def save_params(p): json.dump(p, open(PARAMS_F,'w'), indent=2)

def load_stats():
    if STATS_F.exists():
        try: return json.load(open(STATS_F))
        except: pass
    return {'settled_bets':[],'market_type_stats':{},'clob_stats':{}}

def load_review():
    if REVIEW_F.exists():
        try: return json.load(open(REVIEW_F))
        except: pass
    return {'user_notes':'','evolutions':[]}
def save_review(r): json.dump(r, open(REVIEW_F,'w'), indent=2, ensure_ascii=False)

def load_tp():
    if TP_F.exists():
        try: return json.load(open(TP_F))
        except: pass
    return {
        'tp_enabled': True, 'sl_enabled': True,
        'tp_threshold': 0.75,
        'tp_partial': 0.5,
        'sl_threshold': 0.20,
        'sl_full': True,
        'sl_time_limit': 4320,
        'tp_redeem_trigger': 0.92,
        'user_notes': '',
        'evolutions': []
    }
def save_tp(cfg): json.dump(cfg, open(TP_F,'w'), indent=2)

def load_strategies():
    if STRATS_F.exists():
        try: return json.load(open(STRATS_F))
        except: pass
    return []
def save_strategies(s): json.dump(s, open(STRATS_F,'w'), indent=2, ensure_ascii=False)

def is_stopped(): return STOP_F.exists()
def set_stop(v):
    if v: STOP_F.write_text(datetime.now().isoformat())
    elif STOP_F.exists(): STOP_F.unlink()

# ─── 分类 ──────────────────────────────────────────────────────────────────────
def classify(t):
    t = t.lower()
    if 'bitcoin' in t or 'btc' in t: return 'BTC'
    if 'solana' in t or 'sol ' in t: return 'SOL'
    if any(x in t for x in ['cavaliers','lakers','celtics','bucks','rockets','thunder','nuggets',
        'pistons','timberwolves','76ers','clippers','pelicans','kings','hawks','pacers',
        'nets','wizards','jazz','grizzlies','heat','knicks','spurs']): return 'NBA'
    if any(x in t for x in ['blackhawks','wild','blues','flames','stars','canucks','ducks','jets',
        'sharks','panthers','hurricanes','rangers','red wings','predators','kraken',
        'golden knights','avalanche','lightning']): return 'NHL'
    if any(x in t for x in ['real madrid','barcelona','arsenal','chelsea','bologna','benfica',
        'everton','newcastle','manchester','milan','atletico','laliga','premier','fc ','cup']): return 'Football'
    if any(x in t for x in ['counter-strike','cs2','esport','valorant','dota','league of']): return 'Esports'
    return 'Other'

# ─── 账本 ──────────────────────────────────────────────────────────────────────
def build_ledger(activity):
    by_cid = defaultdict(lambda: {'splits':[],'sells':[],'redeems':[],'title':'','outcome':'','mtype':''})
    for t in activity:
        cid = t.get('conditionId','')
        if not cid: continue
        if t.get('title'):   by_cid[cid]['title']   = t['title']
        if t.get('outcome'): by_cid[cid]['outcome']  = t['outcome']
        by_cid[cid]['mtype'] = classify(t.get('title',''))
        tp = t.get('type','')
        if tp == 'SPLIT':   by_cid[cid]['splits'].append(t)
        elif tp == 'TRADE' and t.get('side') == 'SELL': by_cid[cid]['sells'].append(t)
        elif tp == 'REDEEM': by_cid[cid]['redeems'].append(t)
    ledger = []
    for cid, d in by_cid.items():
        inv = sum(float(s.get('usdcSize') or 0) for s in d['splits'])
        tp_r = sum(float(s.get('usdcSize') or 0) for s in d['sells'])
        rdm_r = sum(float(s.get('usdcSize') or 0) for s in d['redeems'])
        ret = tp_r + rdm_r
        if inv < 0.01: continue
        pnl = ret - inv
        if rdm_r > 0: status = 'win'
        elif tp_r > 0 and pnl > 0: status = 'tp'
        elif tp_r > 0: status = 'sl'
        elif ret == 0: status = 'open'
        else: status = 'partial'
        entry_ts = min((t.get('timestamp', 9e9) for t in d['splits']), default=0)
        last_ts  = max((t.get('timestamp', 0) for t in d['splits']+d['sells']+d['redeems']), default=0)
        ledger.append({'cid':cid,'title':d['title'][:46],'outcome':d['outcome'],'mtype':d['mtype'],
            'invested':inv,'returned':ret,'pnl':pnl,'status':status,'entry_ts':entry_ts,'ts':last_ts})
    return sorted(ledger, key=lambda x: -x['ts'])

def build_daily(ledger):
    days = defaultdict(lambda: {'in':0,'out':0,'win':0,'lose':0,'cnt':0})
    for it in ledger:
        if it['status'] == 'open': continue
        ts = it.get('entry_ts') or it.get('ts', 0)
        if not ts: continue
        day = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
        days[day]['in'] += it['invested']; days[day]['out'] += it['returned']; days[day]['cnt'] += 1
        if it['status'] == 'win': days[day]['win'] += 1
        elif it['status'] in ('sl','partial'): days[day]['lose'] += 1
    return sorted(days.items(), reverse=True)

def build_type_pnl(ledger):
    ts = defaultdict(lambda: {'in':0,'out':0,'cnt':0,'win':0,'lose':0})
    for it in ledger:
        mt = it['mtype']
        ts[mt]['in'] += it['invested']; ts[mt]['out'] += it['returned']; ts[mt]['cnt'] += 1
        if it['status'] == 'win': ts[mt]['win'] += 1
        elif it['status'] in ('sl','partial','open') and it['returned'] == 0: ts[mt]['lose'] += 1
    return dict(ts)

def analyze_positions(pos_list):
    now = datetime.now(timezone.utc)
    pw, aw, am, al = [], [], [], []
    for p in pos_list:
        price = float(p.get('curPrice') or 0); size = float(p.get('size') or 0)
        val   = float(p.get('currentValue') or 0)
        if size < 0.05 and val < 0.05: continue
        try:
            end = p.get('endDate','').replace('Z','+00:00')
            if 'T' not in end: end += 'T23:59:00+00:00'
            mins = (datetime.fromisoformat(end) - now).total_seconds() / 60
        except: mins = 9999
        cost = size * float(p.get('avgPrice') or 0.5)
        item = {'title':p.get('title','')[:44],'outcome':p.get('outcome',''),'price':price,
                'size':size,'val':val,'cost':cost,'pnl_est':val-cost,'mins':mins,
                'redeemable':p.get('redeemable',False),'mtype':classify(p.get('title',''))}
        if mins < 0:
            if price > 0.88: pw.append(item)
        elif price >= 0.65: aw.append(item)
        elif price >= 0.40: am.append(item)
        else: al.append(item)
    return pw, aw, am, al

def parse_finance_log():
    events = []
    if not LOG_F.exists(): return events
    lines = LOG_F.read_text(errors='replace').splitlines()
    for ln in reversed(lines[-1500:]):
        ln = ln.strip()
        if not ln: continue
        ts = ''
        m = re.search(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]', ln)
        if m: ts = m.group(1)[11:]
        else:
            m2 = re.search(r'\[(\d{2}:\d{2}:\d{2})\]', ln)
            if m2: ts = m2.group(1)
        if '✅ 成功' in ln and any(x in ln for x in ['V1','V2','V3','下注','买入']):
            m3 = re.search(r'\|\s*(.+)', ln)
            events.append({'type':'buy_ok','ts':ts,'icon':'🟢','label':'跟单买入成功','detail': m3.group(1).strip()[:50] if m3 else ''})
        elif '止盈' in ln and '✅' in ln:
            m6 = re.search(r'收回\$([\d.]+)', ln)
            events.append({'type':'tp','ts':ts,'icon':'💚','label':f'止盈成功 {("收回$"+m6.group(1)) if m6 else ""}','detail':''})
        elif '止损回收' in ln:
            m7 = re.search(r'亏\$([\d.]+) 回收\$([\d.]+)', ln)
            if m7: events.append({'type':'sl','ts':ts,'icon':'🔶','label':f'止损回收 亏${m7.group(1)}','detail':f'回收${m7.group(2)}'})
        elif '卖出失败' in ln:
            events.append({'type':'sell_fail','ts':ts,'icon':'🔴','label':'卖单失败','detail':'流动性不足或对冲锁死'})
        elif 'MERGE' in ln and '成功' in ln:
            m8 = re.search(r'回收\$([\d.]+)', ln)
            events.append({'type':'merge','ts':ts,'icon':'🔄','label':f'对冲合并 {("回收$"+m8.group(1)) if m8 else ""}','detail':''})
        elif '赎回' in ln and ('成功' in ln or '✅' in ln):
            m9 = re.search(r'~?\$([\d.]+)', ln)
            events.append({'type':'redeem','ts':ts,'icon':'💰','label':f'赎回到账 {("$"+m9.group(1)) if m9 else ""}','detail':''})
        elif '余额不足' in ln:
            events.append({'type':'skip','ts':ts,'icon':'⚪','label':'余额不足','detail':''})
        if len(events) >= 80: break
    return events[:60]


# ─── 动作处理 ─────────────────────────────────────────────────────────────────

WALLET_F = WS / 'iearndot_wallet.json'
PAY_F    = WS / 'iearndot_payment.json'

def load_wallet():
    if WALLET_F.exists():
        try: return json.load(open(WALLET_F))
        except: pass
    return {'profit_wallet':'','profit_threshold':20.0,'profit_auto':'off'}
def save_wallet(w): json.dump(w, open(WALLET_F,'w'), indent=2)

def load_payment():
    if PAY_F.exists():
        try: return json.load(open(PAY_F))
        except: pass
    return {'skillpay_key':'','skillpay_price':0.01,'x402_enabled':'off','x402_wallet':'','x402_price':0.005}
def save_payment(cfg): json.dump(cfg, open(PAY_F,'w'), indent=2)

def do_action(act, qp):
    p = load_params(); rev = load_review(); tp = load_tp(); strats = load_strategies()
    if act == 'stop_bot':
        set_stop(True)
        for nm in ['fast','mid','v1']:
            subprocess.run(['launchctl','stop',f'com.polymarket.{nm}'], capture_output=True)
        return '⏸ 机器人已停止'
    if act == 'start_bot':
        set_stop(False); subprocess.run(['launchctl','start','com.polymarket.mid'], capture_output=True)
        return '▶️ 机器人已重启'
    if act == 'run_fast': subprocess.run(['launchctl','start','com.polymarket.fast']); return '✅ 止盈扫描已触发'
    if act == 'run_mid':  subprocess.run(['launchctl','start','com.polymarket.mid']);  return '✅ 跟单扫描已触发'
    if act == 'run_v1':   subprocess.run(['launchctl','start','com.polymarket.v1']);   return '✅ V1 BTC已触发'
    if act == 'redeem':
        s = WS / 'polymarket_redeem.py'
        if s.exists(): subprocess.Popen(['uv','run','python',str(s)], cwd=POLYCLAW)
        return '✅ 赎回已启动'
    if act == 'merge_hedges':
        s = WS / 'polymarket_take_profit.py'
        if s.exists(): subprocess.Popen(['uv','run','python',str(s),'--merge-only'], cwd=POLYCLAW)
        return '✅ 对冲检测已启动'
    if act == 'refresh_trace':
        s = WS / 'polymarket_v3_tracker.py'
        if s.exists(): subprocess.Popen(['uv','run','python',str(s)], cwd=POLYCLAW)
        return '✅ V3追踪刷新中（约30秒）'
    for k in ['v1','v2','v3','fast']:
        if act == f'toggle_{k}':
            p[f'{k}_enabled'] = not p.get(f'{k}_enabled', True); save_params(p)
            return f'{"✅ 已启用" if p[f"{k}_enabled"] else "⏸ 已暂停"} {k.upper()}'
    if act == 'disable_mtype':
        mt = qp.get('mtype',''); dis = p.get('disabled_market_types',[])
        if mt and mt not in dis: dis.append(mt); p['disabled_market_types'] = dis; save_params(p)
        return f'✅ 已禁用 {mt}'
    if act == 'enable_mtype':
        mt = qp.get('mtype','')
        p['disabled_market_types'] = [x for x in p.get('disabled_market_types',[]) if x != mt]
        save_params(p); return f'✅ 已启用 {mt}'
    if act == 'save_params':
        for k in ['bet_v1','bet_v2_base','bet_v3_base','min_price','max_price','min_liquidity']:
            if k in qp:
                try: p[k] = float(qp[k])
                except: pass
        save_params(p); return '✅ 参数已保存'
    if act == 'save_tp':
        for k in ['tp_threshold','tp_partial','sl_threshold','sl_time_limit','tp_redeem_trigger']:
            if k in qp:
                try: tp[k] = float(qp[k])
                except: pass
        tp['tp_enabled'] = qp.get('tp_enabled','1') == '1'
        tp['sl_enabled'] = qp.get('sl_enabled','1') == '1'
        tp['sl_full']    = qp.get('sl_full','1') == '1'
        if 'tp_notes' in qp: tp['user_notes'] = qp['tp_notes']
        save_tp(tp); return '✅ 止盈止损配置已保存'
    if act == 'evolve_tp':
        notes = qp.get('tp_notes','').strip()
        stats = load_stats(); bets = stats.get('settled_bets',[])
        win_rate = sum(1 for b in bets if b.get('won')) / len(bets) if bets else 0
        if win_rate < 0.40:
            tp['sl_threshold'] = min(tp.get('sl_threshold',0.20) + 0.05, 0.35)
            tp['sl_time_limit'] = max(tp.get('sl_time_limit',4320) - 720, 1440)
        elif win_rate > 0.60:
            tp['tp_threshold'] = max(tp.get('tp_threshold',0.75) - 0.05, 0.65)
        if notes:
            tp.setdefault('evolutions',[]).append({'ts':datetime.now().isoformat(),'note':notes,'win_rate':win_rate})
            tp['user_notes'] = notes
        save_tp(tp); return f'🧬 进化完成（胜率 {win_rate:.0%}，止损线→{tp["sl_threshold"]:.0%}）'
    if act == 'evolve_review':
        notes = qp.get('review_notes','').strip()
        if notes: rev.setdefault('evolutions',[]).append({'ts':datetime.now().isoformat(),'note':notes}); rev['user_notes'] = notes
        p['disabled_market_types'] = ['Football','Other','NBA']
        p['min_liquidity'] = max(p.get('min_liquidity',20000), 20000)
        p['min_price'] = 0.40; save_params(p)
        if notes: save_review(rev)
        s = WS / 'polymarket_evolution.py'
        if s.exists(): subprocess.Popen(['uv','run','python',str(s)], cwd=POLYCLAW)
        return '🧬 进化启动：禁用Football/NBA/Other，提高流动性要求$20K'
    if act == 'save_review':
        notes = qp.get('review_notes','').strip()
        if notes: rev['user_notes'] = notes; save_review(rev)
        return '✅ 意见已保存'
    if act == 'add_strategy':
        name  = qp.get('strat_name','').strip()[:12]
        desc  = qp.get('strat_desc','').strip()
        links = qp.get('strat_links','').strip()
        addr  = qp.get('strat_addr','').strip()
        links_list = [x.strip() for x in re.split(r'[\s,]+', links) if x.strip()]
        addrs_list = [x.strip() for x in re.split(r'[\s,]+', addr) if x.strip()]
        user_note = qp.get('strat_note','').strip()
        if not desc: return '❌ 请填写策略说明'
        existing_codes = [s.get('code','') for s in strats]; max_v = 3
        for c in existing_codes:
            m = re.match(r'V(\d+)', c)
            if m: max_v = max(max_v, int(m.group(1)))
        code = f'V{max_v+1}'
        auto_analysis = _analyze_strategy_input(desc, links_list, addrs_list)
        strat = {'code':code,'name':name or f'{code}自定义','submitted_at':datetime.now().isoformat(),
            'generated_at':datetime.now().isoformat(),'source_desc':desc,
            'source_links':'\n'.join(links_list),'source_addr':'\n'.join(addrs_list),
            'user_note':user_note,'analysis':auto_analysis,'enabled':False,'status':'pending'}
        strats.append(strat); save_strategies(strats)
        return f'✅ 策略 {code}《{strat["name"]}》已生成'
    if act == 'toggle_custom':
        code = qp.get('code','')
        for s in strats:
            if s.get('code') == code: s['enabled'] = not s.get('enabled',False); s['status'] = 'active' if s['enabled'] else 'paused'; break
        save_strategies(strats); return '✅ 已切换'
    if act == 'apply_template':
        tpl = qp.get('tpl','')
        def _add_tpl(name, desc, analysis):
            ec = [s.get('code','') for s in strats]; mv = 3
            for c in ec:
                m = re.match(r'V(\d+)', c)
                if m: mv = max(mv, int(m.group(1)))
            strats.append({'code':f'V{mv+1}','name':name,'submitted_at':datetime.now().isoformat(),
                'generated_at':datetime.now().isoformat(),'source_desc':desc,'source_links':'','source_addr':'',
                'user_note':'官方模板一键应用','analysis':analysis,'enabled':True,'status':'active'})
            save_strategies(strats)
        if tpl == '1':
            p['min_price']=0.40;p['max_price']=0.75;p['bet_v1']=5;p['v1_enabled']=True;save_params(p)
            _add_tpl('BTC趋势模板','官方BTC趋势跟随模板，4h均线上穿入场',
                '市场类型: 加密货币（BTC/ETH）\n入场条件: 4h均线上穿\n止盈线: 0.75\n止损线: 0.25')
            return '✅ 模板已应用：BTC趋势模板'
        elif tpl == '2':
            p['min_price']=0.45;p['max_price']=0.78;save_params(p)
            _add_tpl('电竞大赛模板','CS2/Valorant Major赛前2h入场',
                '市场类型: 电竞（CS2/Valorant）\n入场时机: Major赛前2小时\n价格区间: 0.45-0.65\n止盈线: 0.78')
            return '✅ 模板已应用：电竞大赛模板'
        elif tpl == '3':
            _add_tpl('高胜率跟单模板','跟踪Polymarket榜单前10',
                '市场类型: 综合\n跟单对象: Polymarket榜单前10名\n条件: 近30天胜率>60%\n单注: $5')
            return '✅ 模板已应用：高胜率跟单模板'
        return '❌ 未知模板编号'
    if act == 'save_wallet_config':
        w = load_wallet()
        w['profit_wallet'] = qp.get('profit_wallet','').strip()
        try: w['profit_threshold'] = float(qp.get('profit_threshold', 20))
        except: pass
        w['profit_auto'] = qp.get('profit_auto','off')
        save_wallet(w); return '✅ 安全钱包配置已保存'
    if act == 'save_payment_config':
        cfg = load_payment()
        cfg['skillpay_key'] = qp.get('skillpay_key','').strip()
        try: cfg['skillpay_price'] = float(qp.get('skillpay_price', 0.01))
        except: pass
        cfg['x402_enabled'] = qp.get('x402_enabled','off')
        cfg['x402_wallet'] = qp.get('x402_wallet','').strip()
        try: cfg['x402_price'] = float(qp.get('x402_price', 0.005))
        except: pass
        save_payment(cfg); return '✅ 支付配置已保存'
    return ''


def _analyze_strategy_input(desc, links_list, addrs_list):
    lines = []; desc_l = desc.lower()
    links_list = links_list or []; addrs_list = addrs_list or []
    if 'btc' in desc_l or 'bitcoin' in desc_l:
        lines.append('市场类型: 加密货币（BTC/ETH）'); lines.append('建议: 仅在24h涨幅>2%时开仓')
    elif 'nba' in desc_l or 'basketball' in desc_l:
        lines.append('市场类型: NBA篮球'); lines.append('风险提示: 历史胜率28%，需结合伤病报告')
    elif any(x in desc_l for x in ['soccer','football','premier','laliga']):
        lines.append('市场类型: 足球'); lines.append('风险提示: 历史胜率8%，控制注额≤$3')
    elif any(x in desc_l for x in ['esport','cs2','valorant','dota']):
        lines.append('市场类型: 电竞'); lines.append('建议: 历史胜率60%，每注≤$8')
    else:
        lines.append('市场类型: 其他（需人工确认）')
    if addrs_list:
        lines.append(f'跟单地址: {len(addrs_list)}个')
        for a in addrs_list[:4]: lines.append(f'  - {a[:20]}')
    pm_profiles = [u for u in links_list if 'polymarket.com/@' in u]
    if pm_profiles:
        lines.append(f'Polymarket Profiles: {len(pm_profiles)}个')
        for u in pm_profiles[:4]: lines.append(f'  - {u}')
    if links_list: lines.append(f'参考链接: 已记录 {len(links_list)}个')
    if '止损' in desc or 'stop loss' in desc_l: lines.append('✅ 止损: 已提及，将设置止损线35%')
    if '跟单' in desc or 'copy' in desc_l: lines.append('📋 跟单: 监控目标地址，延迟<15min跟入')
    lines.append(f'--- 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")} ---')
    return '\n'.join(lines)


def get_data():
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        f_pos  = ex.submit(fetch, f'https://data-api.polymarket.com/positions?user={MY_ADDR}&sizeThreshold=0&limit=100')
        f_act  = ex.submit(fetch, f'https://data-api.polymarket.com/activity?user={MY_ADDR}&limit=500', 30)
        f_bal  = ex.submit(get_balance)
        f_jobs = ex.submit(get_jobs)
        try: pos = f_pos.result(timeout=10)
        except: pos = []
        try: activity = f_act.result(timeout=10)
        except: activity = []
        try: balance = f_bal.result(timeout=8)
        except: balance = 0.0
        try: jobs = f_jobs.result(timeout=5)
        except: jobs = {}
    params = load_params(); stats = load_stats(); review = load_review()
    tp_cfg = load_tp(); strats = load_strategies()
    wallet = load_wallet(); payment = load_payment()
    ledger = build_ledger(activity); fin_log = parse_finance_log()
    pw, aw, am, al = analyze_positions(pos)
    daily = build_daily(ledger); type_pnl = build_type_pnl(ledger)
    splits  = [t for t in activity if t.get('type')=='SPLIT']
    redeems = [t for t in activity if t.get('type')=='REDEEM']
    sells   = [t for t in activity if t.get('type')=='TRADE' and t.get('side')=='SELL']
    total_in  = sum(float(t.get('usdcSize') or 0) for t in splits)
    total_rdm = sum(float(t.get('usdcSize') or 0) for t in redeems)
    total_sell = sum(float(t.get('usdcSize') or 0) for t in sells)
    bets = stats.get('settled_bets',[])
    v3_trace = []
    if TRACE_F.exists():
        try: v3_trace = json.load(open(TRACE_F))
        except: pass
    accts = []
    if V3ACC_F.exists():
        try: accts = json.load(open(V3ACC_F))
        except: pass
    return dict(
        balance=balance, pw=pw, aw=aw, am=am, al=al,
        pending_amt=sum(p['size'] for p in pw), active_val=sum(p['val'] for p in aw+am+al),
        total_in=total_in, total_out=total_rdm+total_sell,
        total_rdm=total_rdm, total_sell=total_sell, pnl_all=total_rdm+total_sell-total_in,
        params=params, stats=stats, jobs=jobs, ledger=ledger, fin_log=fin_log,
        daily=daily, type_pnl=type_pnl, settled_n=len(bets),
        won_n=sum(1 for b in bets if b.get('won')),
        accts=accts, v3_trace=v3_trace, review=review, tp_cfg=tp_cfg, strats=strats,
        wallet=wallet, payment=payment,
        disabled=params.get('disabled_market_types',[]),
        stopped=is_stopped(), now=datetime.now().strftime('%H:%M:%S'),
    )


CSS = r'''
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0b0d14;color:#e0e0e0;font-size:13px}
a{color:inherit;text-decoration:none}
.hdr{background:#13162a;padding:10px 20px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #1e2235;position:sticky;top:0;z-index:200}
.logo{display:flex;align-items:center;gap:10px}
.logo-icon{width:34px;height:34px;border-radius:50%;background:linear-gradient(135deg,#059669,#34d399);display:flex;align-items:center;justify-content:center;font-weight:900;font-size:13px;color:#fff;flex-shrink:0;letter-spacing:-.5px}
.logo-name{font-size:16px;font-weight:800;color:#34d399;letter-spacing:-.3px;line-height:1}
.logo-sub{font-size:10px;color:#555;margin-top:2px}
.tabs{display:flex;background:#0e1020;border-bottom:2px solid #1e2235;padding:0 20px;overflow-x:auto;flex-wrap:nowrap}
.tab{padding:9px 15px;cursor:pointer;color:#555;font-size:12px;font-weight:600;border-bottom:2px solid transparent;margin-bottom:-2px;transition:.15s;white-space:nowrap;user-select:none}
.tab:hover{color:#aaa}.tab.active{color:#818cf8;border-bottom-color:#818cf8}
.page{display:none;padding:14px 20px}.page.active{display:block}
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:9px;margin-bottom:12px}
.kpi{background:#13162a;border-radius:9px;padding:12px 14px;border:1px solid #1e2235}
.kpi h4{font-size:10px;color:#444;text-transform:uppercase;letter-spacing:.7px;margin-bottom:7px}
.kpi .v{font-size:22px;font-weight:800;letter-spacing:-1px}
.kpi .sub{color:#444;font-size:11px;margin-top:3px}
.g{color:#34d399}.y{color:#fbbf24}.r{color:#f87171}.b{color:#60a5fa}.pu{color:#a78bfa}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.three{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
.card{background:#13162a;border-radius:9px;padding:13px;border:1px solid #1e2235;margin-bottom:11px}
.card h3{font-size:12px;color:#888;margin-bottom:9px;padding-left:7px;border-left:3px solid #818cf8}
table{width:100%;border-collapse:collapse}
th{background:#1a1e30;padding:6px 8px;text-align:left;font-size:10px;color:#555;text-transform:uppercase;font-weight:700}
td{padding:6px 8px;border-bottom:1px solid #0f1117;font-size:12px;vertical-align:middle}
tr:last-child td{border:none}tr:hover>td{background:#1a1e30}
.btn{display:inline-flex;align-items:center;gap:4px;padding:5px 12px;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600;border:none;margin:2px;transition:.12s;text-decoration:none}
.btn-p{background:#4338ca;color:#fff}.btn-g{background:#14532d;color:#4ade80}
.btn-r{background:#7f1d1d;color:#fca5a5}.btn-gray{background:#1e2235;color:#888}
.btn-o{background:#7c2d12;color:#fed7aa}.btn-pu{background:#3b0764;color:#e9d5ff}
.badge{display:inline-flex;align-items:center;padding:2px 7px;border-radius:10px;font-size:11px;font-weight:600}
.bdg{background:#1a1e30;color:#888}.bdgg{background:#14532d;color:#4ade80}.bdgy{background:#713f12;color:#fbbf24}
.bdgr{background:#7f1d1d;color:#fca5a5}.bdgb{background:#1e3a5f;color:#60a5fa}.bdgp{background:#2e1065;color:#a78bfa}
.pnl-pos{color:#34d399;font-weight:700}.pnl-neg{color:#f87171;font-weight:700}
.alert{background:#431407;border:1px solid #7c2d12;border-radius:8px;padding:10px 14px;margin-bottom:8px;color:#fdba74;display:flex;align-items:center;gap:10px}
.info{background:#1e3a5f22;border:1px solid #1e3a5f;border-radius:8px;padding:10px 14px;margin-bottom:8px;color:#93c5fd;display:flex;align-items:center;gap:10px}
.ok{background:#14532d22;border:1px solid #166534;border-radius:8px;padding:10px 14px;margin-bottom:8px;color:#4ade80;display:flex;align-items:center;gap:10px}
.dot-on{width:7px;height:7px;border-radius:50%;background:#34d399;display:inline-block;animation:pulse 2s infinite;margin-right:3px}
.dot-off{width:7px;height:7px;border-radius:50%;background:#333;display:inline-block;margin-right:3px}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.sh{font-size:12px;color:#818cf8;font-weight:700;margin:12px 0 7px;padding-bottom:3px;border-bottom:1px solid #1e2235}
textarea,input[type=text],input[type=url],input[type=password]{font-family:inherit;background:#1a1e30;border:1px solid #2a2d3a;color:#eee;padding:6px 9px;border-radius:6px;font-size:12px}
input[type=number]{background:#1a1e30;border:1px solid #2a2d3a;color:#eee;padding:5px 8px;border-radius:5px;width:90px;font-size:12px}
select{background:#1a1e30;border:1px solid #2a2d3a;color:#eee;padding:5px 8px;border-radius:5px;font-size:12px}
label{font-size:12px;color:#666;margin-right:4px}
.ev-box{height:480px;overflow-y:auto}
.strat-card{background:#0e1020;border:1px solid #1e2235;border-radius:8px;padding:12px;margin-bottom:10px}
.strat-card.active-strat{border-color:#818cf8}
.subtabs{display:flex;gap:4px;margin-bottom:14px}
.subtab{padding:5px 14px;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600;color:#555;background:#0e1020;border:1px solid #1e2235}
.subtab.stactive{background:#4338ca;color:#fff;border-color:#4338ca}
.subpage{display:none}.subpage.stactive{display:block}
.disclaimer{background:#1a1200;border:1px solid #713f12;border-radius:7px;padding:8px 12px;font-size:11px;color:#fbbf24;margin-bottom:10px}
.tpl-card{background:#0e1020;border:1px solid #1e2235;border-radius:8px;padding:14px;margin-bottom:10px}
.coming-soon{background:#0e1020;border:2px dashed #2a2d3a;border-radius:8px;padding:30px;text-align:center;color:#333;margin-bottom:10px}
.warn-box{background:#450a0a;border:1px solid #991b1b;border-radius:8px;padding:10px 14px;margin-bottom:10px;color:#fca5a5;font-size:12px;line-height:1.7}
.pay-box{background:#0c1a2e;border:1px solid #1e3a5f;border-radius:8px;padding:10px 14px;margin-bottom:10px;color:#93c5fd;font-size:12px;line-height:1.7}
pre{white-space:pre-wrap;word-break:break-word;font-family:inherit;font-size:11px;color:#aaa;line-height:1.7}
'''

def mtype_badge(mt):
    cls = {'BTC':'bdgb','SOL':'bdgb','NBA':'bdgr','NHL':'bdgp','Football':'bdgr','Esports':'bdgy'}.get(mt,'bdg')
    return f'<span class="badge {cls}">{mt}</span>'

def pnl_cell(v):
    c = 'pnl-pos' if v >= 0 else 'pnl-neg'
    return f'<span class="{c}">{"+" if v>=0 else ""}{v:.2f}</span>'

def jb_status(nm, jobs):
    info = jobs.get(nm, {}); run = info.get('run')
    dot = '<span class="dot-on"></span>' if run else '<span class="dot-off"></span>'
    return dot + (' 运行中' if run else ' 待机')


LESSONS = [
    ('critical','🔴','Football跟单 -$134，胜率仅8%',
     '投$142回收$8。V3目标账号是专业对冲，裸跟导致全输。\n教训: 足球单场赢率低，对冲账号本金远大于我们。'),
    ('critical','🔴','Other类小球会 -$107，回收率0.7%',
     '投$107几乎全损。非主流市场CLOB几乎全失败。\n教训: 非主流市场流动性极差，必须完全禁止。'),
    ('high','🟠','NBA跟单 -$19，胜率28%',
     '投$116回收$97，18笔5胜13负。\n教训: NBA需结合伤病报告，纯价格跟单不可靠。'),
    ('high','🟠','对冲锁死各损$9',
     '同场球两边都买，止损无法执行。\n修复: 已加conditionId去重+自动MERGE回收。'),
    ('medium','🟡','BTC方向 +$1.78，胜率35%',
     '投$110回收$112，勉强打平。\n教训: BTC方向策略仅在单边上涨行情有效。'),
    ('medium','🟡','CLOB失败成本被低估',
     '早期CLOB成功率52%，流动性<$15K时更低。\n修复: 流动性门槛提高至$20K。'),
]
WHAT_WORKED = [
    '✅ Esports跟单: 5笔3胜2负，60%胜率，值得保留',
    '✅ 链上赎回系统: $159待结算仓位成功赎回',
    '✅ MERGE自动回收: 对冲锁死合并回收$9本金',
    '✅ 自进化引擎: NBA 25%胜率被自动检测并禁用',
    '✅ 止盈架构基础: BTC高频市场止盈多笔成功',
]


def h_pos_rows(items, empty='暂无'):
    if not items: return f'<tr><td colspan="7" style="color:#333;text-align:center;padding:12px">{empty}</td></tr>'
    rows = ''
    for it in items:
        h = f'{it["mins"]/60:.0f}h' if it["mins"] > 60 else (f'{it["mins"]:.0f}m' if it["mins"] > 0 else '已过期')
        pc = 'g' if it['price'] > 0.7 else ('y' if it['price'] > 0.4 else 'r')
        rdm = '<span class="badge bdgg" style="font-size:10px">赎</span>' if it.get('redeemable') else ''
        rows += (f'<tr><td>{mtype_badge(it["mtype"])}</td><td><b>{it["outcome"]}</b></td>'
                 f'<td class="{pc}">{it["price"]:.0%}</td><td>${it["val"]:.2f}</td>'
                 f'<td style="color:#555">${it["cost"]:.2f}</td><td>{pnl_cell(it["pnl_est"])}</td>'
                 f'<td>{h} {rdm}</td></tr>')
    return rows

def h_ledger_rows(items):
    if not items: return '<tr><td colspan="8" style="color:#333;text-align:center;padding:12px">暂无</td></tr>'
    SM = {'win':('💰','bdgg','已结算'),'tp':('💚','bdgg','止盈卖出'),'sl':('🔶','bdgy','止损回收'),'open':('🔵','bdgb','持仓中'),'partial':('🟡','bdgy','部分回收')}
    rows = ''
    for it in items[:80]:
        ic, cl, lb = SM.get(it['status'], ('⚪','bdg',''))
        dt = datetime.fromtimestamp(it['entry_ts']).strftime('%m-%d %H:%M') if it['entry_ts'] else ''
        rs = f'${it["returned"]:.2f}' if it['returned'] > 0 else '—'
        rows += (f'<tr><td style="color:#444;white-space:nowrap">{dt}</td><td>{mtype_badge(it["mtype"])}</td>'
                 f'<td style="max-width:150px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;color:#888">{it["title"]}</td>'
                 f'<td><b>{it["outcome"]}</b></td><td>${it["invested"]:.2f}</td><td>{rs}</td>'
                 f'<td>{pnl_cell(it["pnl"])}</td><td><span class="badge {cl}">{ic} {lb}</span></td></tr>')
    return rows

def h_daily_rows(daily):
    if not daily: return '<tr><td colspan="6" style="color:#333;text-align:center;padding:12px">暂无</td></tr>'
    rows = ''
    for day, s in daily[:14]:
        pnl = s['out'] - s['in']; t = s['win'] + s['lose']
        wr = s['win'] / t * 100 if t > 0 else 0
        wrc = 'g' if wr >= 55 else ('y' if wr >= 40 else 'r')
        rows += (f'<tr><td><b>{day}</b></td><td>${s["in"]:.2f}</td><td>${s["out"]:.2f}</td>'
                 f'<td>{pnl_cell(pnl)}</td><td>{s["win"]}胜 {s["lose"]}负</td><td class="{wrc}">{wr:.0f}%</td></tr>')
    return rows

def h_type_rows(tp, disabled, show_btn=True):
    if not tp: return '<tr><td colspan="7" style="color:#333;text-align:center;padding:12px">暂无</td></tr>'
    rows = ''
    for mt, s in sorted(tp.items(), key=lambda x: x[1]['out']-x[1]['in']):
        pnl = s['out'] - s['in']; t = s['win'] + s['lose']
        wr = s['win'] / t * 100 if t > 0 else 0
        is_dis = mt in disabled
        dis_tag = '<span class="badge bdgr" style="font-size:9px">禁</span>' if is_dis else ''
        btn = ''
        if show_btn:
            btn = (f'<a class="btn btn-g" style="padding:2px 7px;font-size:10px" href="/?a=enable_mtype&mtype={mt}">启用</a>' if is_dis
                   else f'<a class="btn btn-r" style="padding:2px 7px;font-size:10px" href="/?a=disable_mtype&mtype={mt}">禁用</a>')
        rows += (f'<tr><td>{mtype_badge(mt)} {dis_tag}</td><td>${s["in"]:.2f}</td><td>${s["out"]:.2f}</td>'
                 f'<td>{pnl_cell(pnl)}</td><td>{s["win"]}W {s["lose"]}L</td>'
                 f'<td class="{"g" if wr>=55 else ("y" if wr>=40 else "r")}">{wr:.0f}%</td><td>{btn}</td></tr>')
    return rows

def h_evlog(fin_log):
    if not fin_log: return '<div style="color:#333;text-align:center;padding:30px">暂无活动</div>'
    COLORS = {'buy_ok':'#34d399','tp':'#4ade80','sl':'#fbbf24','redeem':'#818cf8',
              'sell_fail':'#f87171','merge':'#38bdf8','skip':'#333','bet':'#60a5fa'}
    html = ''
    for ev in fin_log:
        c = COLORS.get(ev['type'], '#444')
        detail = f'<div style="font-size:11px;color:#555;margin-top:2px">{ev.get("detail","")}</div>' if ev.get('detail') else ''
        html += (f'<div style="display:flex;gap:10px;align-items:flex-start;padding:8px 0;'
                 f'border-bottom:1px solid #0f1117;border-left:3px solid {c};padding-left:10px;margin-bottom:2px">'
                 f'<span style="font-size:16px;min-width:22px">{ev["icon"]}</span>'
                 f'<div style="flex:1"><div style="font-weight:700;font-size:12px">{ev["label"]}</div>{detail}</div>'
                 f'<span style="font-size:10px;color:#333;white-space:nowrap">{ev["ts"]}</span></div>')
    return html

def h_v3_trace(traces, accts):
    if not traces:
        return '<p style="color:#333;padding:16px;text-align:center">暂无数据 — <a href="/?a=refresh_trace" style="color:#818cf8">点击刷新</a></p>'
    rows = ''
    acct_map = {a.get('name',''): a.get('addr','') for a in accts}
    for t in traces[:30]:
        pd = t.get('price_diff'); my_pnl = t.get('my_pnl', 0)
        pd_html = ''
        if pd is not None:
            c = '#f87171' if pd > 0.02 else ('#34d399' if pd < -0.01 else '#888')
            pd_html = f'<span style="color:{c}">{"⚠️+" if pd>0.02 else ("✅" if pd<-0.01 else "")}{pd:.3f}</span>'
        acc = t.get('account',''); addr = acct_map.get(acc,'')
        pm_link  = f'https://polymarket.com/profile/{addr}' if addr else '#'
        pol_link = f'https://polygonscan.com/address/{addr}' if addr else '#'
        dt = datetime.fromtimestamp(t['my_entry_ts']).strftime('%m-%d %H:%M') if t.get('my_entry_ts') else '—'
        src_c = 'g' if t.get('src_pnl', 0) >= 0 else 'r'
        rows += (f'<tr><td><a href="{pm_link}" target="_blank" style="color:#818cf8">🔗 {acc[:10]}</a><br>'
                 f'<a href="{pol_link}" target="_blank" style="color:#444;font-size:10px">Scan ↗</a></td>'
                 f'<td style="max-width:140px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;color:#888">{t.get("title","")}</td>'
                 f'<td><b>{t.get("outcome","")}</b></td>'
                 f'<td>${t.get("src_avg",0):.3f}<br><span class="{src_c}">{t.get("src_pnl_pct",0):+.1f}%</span></td>'
                 f'<td>${t.get("my_avg",0):.3f}<br><span style="color:#444">{dt}</span></td>'
                 f'<td>{pd_html}</td><td>${t.get("src_cur",0):.3f}</td>'
                 f'<td>${t.get("my_val",0):.2f}</td><td>{pnl_cell(my_pnl)}</td></tr>')
    return (f'<table><tr><th>账号</th><th>市场</th><th>方向</th><th>目标均价/PnL</th>'
            f'<th>我方均价/时间</th><th>价差</th><th>现价</th><th>我市值</th><th>我盈亏</th></tr>{rows}</table>')

