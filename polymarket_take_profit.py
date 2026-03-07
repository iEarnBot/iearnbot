#!/usr/bin/env python3
"""
Polymarket 动态止盈卖出引擎
"见好就收" - 眼疾手快，蚊子腿也是肉

止盈规则：
- 高频仓位（<1h）：净收益 > 20% 即卖出
- 短期仓位（1-6h）：净收益 > $2 或 > 15% 即卖出
- 中期仓位（6-24h）：净收益 > $3 或 > 20% 即卖出
- 长期仓位（>24h）：净收益 > $5 或 > 25% 即卖出
- 止损：亏损 > 60% 且距结算 > 2h → 卖出回收残值
"""

import asyncio
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# 加入 polyclaw skill 路径
SKILL_DIR = Path.home() / '.openclaw/skills/polyclaw'
sys.path.insert(0, str(SKILL_DIR / 'scripts'))
sys.path.insert(0, str(SKILL_DIR / 'lib'))
sys.path.insert(0, str(SKILL_DIR))

WORKSPACE = Path.home() / '.openclaw/workspace'
LOG_FILE = WORKSPACE / 'polymarket_bot.log'
MY_ADDR = '0x2c6c1BF553A72d2d17f560FdeD8287b28659DeB8'
GAS_COST = 0.05        # Gas + 滑点
CLOB_OK_RATE = 0.52    # 当前CLOB成功率（52%，薄市场FOK失败率高）

def real_cost_per_token(entry_price: float) -> float:
    """摊入CLOB失败损耗后的每token真实成本"""
    # 买YES时：split $X → YES X枚 + NO X枚
    # NO那边 CLOB卖出只有52%成功，48%直接损失
    no_loss = (1 - entry_price) * (1 - CLOB_OK_RATE)
    return entry_price + no_loss

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(LOG_FILE, 'a') as f:
        f.write(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {msg}\n')

def fetch(url, timeout=8):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def check_take_profit(cur_price, entry_price, cur_val, size, mins_remaining):
    """
    基于真实成本（摊入CLOB失败损耗）的止盈判断
    Returns: (should_sell, reason, sell_price)
    """
    if cur_price <= 0.01 or entry_price <= 0.01 or size <= 0:
        return False, '', 0

    # 高价位入场(>=0.70)：等满赔更合算，不主动卖
    if entry_price >= 0.70:
        return False, '', 0

    # 价格已接近满赔(>=0.95)：无买方，等链上结算
    if cur_price >= 0.95:
        return False, '', 0

    # 真实每token成本（含CLOB失败摊销）
    real_cost = real_cost_per_token(entry_price)
    pnl_per_token = cur_price - real_cost
    pnl_pct = pnl_per_token / real_cost
    pnl_usd = pnl_per_token * size
    net_pnl = pnl_usd - GAS_COST

    if net_pnl <= 0:
        # 未覆盖真实成本，继续持有
        pass
    elif mins_remaining < 60:
        # 高频(<1h)：真实净盈 >20%
        if pnl_pct >= 0.20:
            return True, f'高频止盈 成本${real_cost:.3f} 净+${net_pnl:.2f}({pnl_pct*100:.0f}%)', cur_price
    elif mins_remaining < 360:
        # 短期(1-6h)：净盈 >$1.5 或 >15%
        if net_pnl >= 1.5 or pnl_pct >= 0.15:
            return True, f'短期止盈 成本${real_cost:.3f} 净+${net_pnl:.2f}({pnl_pct*100:.0f}%)', cur_price
    elif mins_remaining < 1440:
        # 中期(6-24h)：净盈 >$2.5 或 >20%
        if net_pnl >= 2.5 or pnl_pct >= 0.20:
            return True, f'中期止盈 成本${real_cost:.3f} 净+${net_pnl:.2f}({pnl_pct*100:.0f}%)', cur_price
    else:
        # 长期(>24h)：净盈 >$4 或 >25%
        if net_pnl >= 4.0 or pnl_pct >= 0.25:
            return True, f'长期止盈 成本${real_cost:.3f} 净+${net_pnl:.2f}({pnl_pct*100:.0f}%)', cur_price

    # 止损：亏损超过真实成本50% 且距结算>2h → 回收残值
    if pnl_per_token <= -real_cost * 0.50 and mins_remaining > 120:
        recover = cur_val - GAS_COST
        if recover > 0.30:
            return True, f'止损回收 亏${-pnl_usd:.2f} 回收${recover:.2f}', cur_price

    return False, '', 0

def do_sell(token_id: str, amount: float, price: float, dry_run: bool) -> bool:
    """调用 ClobClientWrapper.sell_fok 卖出"""
    if dry_run:
        log(f'  [DRY SELL] token:{token_id[:16]}... {amount:.3f}tok @ ${price:.3f}')
        return True
    try:
        from clob_client import ClobClientWrapper
        from wallet_manager import WalletManager

        wallet = WalletManager()
        if not wallet.is_unlocked:
            log('  ❌ 钱包未解锁（POLYCLAW_PRIVATE_KEY 未设置）')
            return False

        clob = ClobClientWrapper(
            wallet.get_unlocked_key(),
            wallet.address,
        )
        order_id, filled, error = clob.sell_fok(token_id, amount, price)
        if filled:
            log(f'  ✅ 卖出成功 order:{order_id}')
            return True
        else:
            log(f'  ❌ 卖出失败: {error}')
            return False
    except Exception as e:
        log(f'  ❌ 卖出异常: {e}')
        return False

def get_token_id_for_outcome(condition_id: str, outcome: str) -> str:
    """从 gamma API 获取 token_id"""
    try:
        data = fetch(f'https://gamma-api.polymarket.com/markets?conditionId={condition_id}', timeout=6)
        markets = data if isinstance(data, list) else [data]
        for m in markets:
            tokens = m.get('clobTokenIds', '[]')
            if isinstance(tokens, str):
                tokens = json.loads(tokens)
            outcomes = m.get('outcomes', '[]')
            if isinstance(outcomes, str):
                outcomes = json.loads(outcomes)
            if tokens and outcomes:
                for i, o in enumerate(outcomes):
                    if o.lower() == outcome.lower() and i < len(tokens):
                        return tokens[i]
        return ''
    except:
        return ''

def do_merge(condition_id: str, yes_asset: str, no_asset: str, amount_e6: int, dry_run: bool) -> float:
    """MERGE 对冲仓位回收本金。返回回收金额（USDC）"""
    if dry_run:
        log(f'  [DRY MERGE] cid:{condition_id[:16]}... {amount_e6/1e6:.4f} tokens → ${amount_e6/1e6:.4f}')
        return amount_e6 / 1e6
    try:
        import os
        from web3 import Web3
        from eth_account import Account

        pk  = os.environ.get('POLYCLAW_PRIVATE_KEY','') or open(Path.home()/'.openclaw/skills/polyclaw/.env').read().split('POLYCLAW_PRIVATE_KEY=')[1].split('\n')[0]
        rpc = os.environ.get('CHAINSTACK_NODE','') or open(Path.home()/'.openclaw/skills/polyclaw/.env').read().split('CHAINSTACK_NODE=')[1].split('\n')[0]
        w3  = Web3(Web3.HTTPProvider(rpc))
        acct = Account.from_key(pk)
        addr = acct.address

        CTF_ADDR = '0x4D97DCd97eC945f40cF65F87097ACe5EA0476045'
        USDC_E   = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
        CTF_ABI  = [{"inputs":[{"name":"collateralToken","type":"address"},{"name":"parentCollectionId","type":"bytes32"},
                    {"name":"conditionId","type":"bytes32"},{"name":"partition","type":"uint256[]"},
                    {"name":"amount","type":"uint256"}],
                    "name":"mergePositions","outputs":[],"stateMutability":"nonpayable","type":"function"}]
        ctf = w3.eth.contract(address=w3.to_checksum_address(CTF_ADDR), abi=CTF_ABI)

        cid_bytes  = bytes.fromhex(condition_id[2:] if condition_id.startswith('0x') else condition_id)
        nonce      = w3.eth.get_transaction_count(addr)
        gas_price  = int(w3.eth.gas_price * 1.2)
        tx = ctf.functions.mergePositions(
            w3.to_checksum_address(USDC_E), b'\x00'*32, cid_bytes, [1, 2], amount_e6
        ).build_transaction({'from': addr, 'nonce': nonce, 'gas': 200000, 'gasPrice': gas_price})
        signed = w3.eth.account.sign_transaction(tx, pk)
        txhash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(txhash, timeout=60)
        recovered = amount_e6 / 1e6
        log(f'  ✅ MERGE 成功 回收${recovered:.4f} tx:{txhash.hex()[:16]}...')
        return recovered
    except Exception as e:
        log(f'  ❌ MERGE 失败: {e}')
        return 0.0

async def run_take_profit(dry_run=False, verbose=False):
    """主扫描：检查所有持仓，执行止盈/止损/MERGE"""
    log('--- 止盈扫描 ---')
    now = datetime.now(timezone.utc)

    try:
        positions = fetch(
            f'https://data-api.polymarket.com/positions?user={MY_ADDR}&sizeThreshold=0&limit=100',
            timeout=8)
    except Exception as e:
        log(f'获取持仓失败: {e}')
        return 0

    # ── 预处理：检测对冲仓（同一 conditionId 同时持有两个方向）──────────────
    # 按 conditionId 分组
    cid_positions = {}
    for p in positions:
        cid = p.get('conditionId','')
        if not cid: continue
        if cid not in cid_positions:
            cid_positions[cid] = []
        cid_positions[cid].append(p)

    merged_cids = set()
    for cid, ps in cid_positions.items():
        if len(ps) < 2: continue
        # 同一 conditionId 多个方向 = 对冲锁死
        sizes  = [float(p.get('size',0)) for p in ps]
        assets = [p.get('asset','') for p in ps]
        min_sz = min(sizes)
        if min_sz < 0.01: continue
        names  = [p.get('outcome','?') for p in ps]
        log(f'  ⚠️  检测到对冲仓: {" vs ".join(names)} 各{min_sz:.2f}tok → MERGE 回收本金')
        # 找 YES(outcomeIndex=0) 和 NO(outcomeIndex=1)
        yes_asset = no_asset = ''
        for p in ps:
            idx = int(p.get('outcomeIndex', -1))
            if idx == 0: yes_asset = p.get('asset','')
            elif idx == 1: no_asset = p.get('asset','')
        if not yes_asset or not no_asset:
            # fallback: 用第一个/第二个
            yes_asset, no_asset = assets[0], assets[1]
        amount_e6 = int(min_sz * 1e6)
        do_merge(cid, yes_asset, no_asset, amount_e6, dry_run)
        merged_cids.add(cid)

    sold_count = 0
    recovered = 0.0

    for p in positions:
        # 跳过已 MERGE 的仓位
        if p.get('conditionId','') in merged_cids:
            continue
        cur_price  = float(p.get('curPrice') or 0)
        cur_val    = float(p.get('currentValue') or 0)
        size       = float(p.get('size') or 0)
        outcome    = p.get('outcome', '')
        token_id   = p.get('asset', '')        # ← 直接用 asset 字段！
        cid        = p.get('conditionId', '')
        title      = p.get('title', '')[:40]

        # 用精确的 avgPrice（真实入场均价）
        entry_price = float(p.get('avgPrice') or 0)
        # 也可以用 API 提供的精确盈亏
        pct_pnl    = float(p.get('percentPnl') or 0)   # 已计算好的百分比
        cash_pnl   = float(p.get('cashPnl') or 0)      # 已计算好的美元盈亏

        if cur_val < 0.30 or size < 0.1 or not token_id:
            continue

        # price > 0.95：市场已认定结果，无买方，直接等链上满赔，跳过
        if cur_price >= 0.95:
            if verbose:
                log(f'  ⏳ {outcome:12} ${cur_price:.3f} 已接近满赔，等链上结算 | {title}')
            continue

        # 结算时间
        try:
            end = p.get('endDate', '').replace('Z', '+00:00')
            if 'T' not in end: end += 'T23:59:00+00:00'
            mins = (datetime.fromisoformat(end) - now).total_seconds() / 60
        except:
            continue

        if mins < 5:  # 5分钟内直接等结算
            continue

        # 用精确入场价，fallback 到合理估算
        if entry_price <= 0:
            entry_price = cur_price * 0.80 if cur_price > 0 else 0.50

        should_sell, reason, sell_price = check_take_profit(
            cur_price, entry_price, cur_val, size, mins)

        if verbose or should_sell:
            icon = '🎯' if should_sell else '⏳'
            log(f'  {icon} {outcome:12} ${cur_price:.3f} entry${entry_price:.3f} '
                f'pnl${cash_pnl:+.2f}({pct_pnl:+.0f}%) ${cur_val:.2f} {mins:.0f}min | {title}')
            if reason:
                log(f'     → {reason}')

        if should_sell:
            ok = do_sell(token_id, size, cur_price, dry_run)
            if ok:
                sold_count += 1
                recovered += cur_val

    log(f'止盈完成: 卖出{sold_count}笔 回收~${recovered:.2f}')
    return sold_count

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Polymarket 止盈引擎')
    parser.add_argument('--dry', action='store_true', help='模拟运行')
    parser.add_argument('--verbose', action='store_true', help='显示所有持仓')
    args = parser.parse_args()
    asyncio.run(run_take_profit(args.dry, args.verbose))
