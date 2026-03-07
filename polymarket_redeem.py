#!/usr/bin/env python3
"""
Polymarket 链上 Redeem — 直接调用 CTF 合约赎回已结算仓位
"""
import os, sys, time, json
from pathlib import Path
from collections import defaultdict

SKILL_DIR = Path.home() / '.openclaw/skills/polyclaw'
sys.path.insert(0, str(SKILL_DIR / 'lib'))
sys.path.insert(0, str(SKILL_DIR / 'scripts'))

def redeem_all():
    import urllib.request
    from web3 import Web3
    from wallet_manager import WalletManager

    addr_str = '0x2c6c1BF553A72d2d17f560FdeD8287b28659DeB8'
    rpc = os.environ.get('CHAINSTACK_NODE','')
    w3  = Web3(Web3.HTTPProvider(rpc))
    wm  = WalletManager()
    key = wm.get_unlocked_key()

    # CTF 合约 (ERC1155)
    CTF_ADDR   = Web3.to_checksum_address('0x4D97DCd97eC945f40cF65F87097ACe5EA0476045')
    # redeemPositions(collateral, parentCollectionId, conditionId, indexSets)
    CTF_ABI = [{
        "name": "redeemPositions",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "collateralToken", "type": "address"},
            {"name": "parentCollectionId", "type": "bytes32"},
            {"name": "conditionId", "type": "bytes32"},
            {"name": "indexSets", "type": "uint256[]"}
        ],
        "outputs": []
    }, {
        "name": "payoutDenominator",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "conditionId", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "uint256"}]
    }]

    USDC_E = Web3.to_checksum_address('0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174')
    ZERO32 = b'\x00' * 32

    ctf = w3.eth.contract(address=CTF_ADDR, abi=CTF_ABI)

    # 获取可赎回仓位
    r = urllib.request.urlopen(urllib.request.Request(
        f'https://data-api.polymarket.com/positions?user={addr_str}&sizeThreshold=0&limit=100',
        headers={'User-Agent':'Mozilla/5.0'}), timeout=10)
    positions = json.loads(r.read())

    # 按 conditionId 分组
    by_cid = defaultdict(list)
    for p in positions:
        if p.get('redeemable') and float(p.get('size') or 0) > 0.1:
            by_cid[p['conditionId']].append(p)

    print(f'找到 {len(by_cid)} 个可赎回 conditionId，共 {sum(len(v) for v in by_cid.values())} 个仓位')

    total_redeemed = 0
    for cid_hex, plist in by_cid.items():
        try:
            # 验证链上已结算（payoutDenominator > 0）
            cid_bytes = bytes.fromhex(cid_hex.replace('0x',''))
            denom = ctf.functions.payoutDenominator(cid_bytes).call()
            if denom == 0:
                print(f'  ⏳ {cid_hex[:16]}... 链上未结算，跳过')
                continue

            # indexSets: YES=1, NO=2, both=3
            # 我们持有哪些outcome
            index_sets = []
            for p in plist:
                idx = int(p.get('outcomeIndex', 0))
                index_sets.append(1 << idx)  # YES=bit0=1, NO=bit1=2
            # 去重
            index_sets = list(set(index_sets))

            title = plist[0].get('title','')[:40]
            size_total = sum(float(p.get('size') or 0) for p in plist)
            print(f'  赎回: {title}  indexSets:{index_sets}  ~${size_total:.2f}')

            nonce = w3.eth.get_transaction_count(Web3.to_checksum_address(addr_str))
            tx = ctf.functions.redeemPositions(
                USDC_E, ZERO32, cid_bytes, index_sets
            ).build_transaction({
                'from': Web3.to_checksum_address(addr_str),
                'nonce': nonce,
                'gas': 200000,
                'maxFeePerGas': w3.eth.gas_price * 2,
                'maxPriorityFeePerGas': Web3.to_wei(30, 'gwei'),
                'chainId': 137,
            })
            signed = w3.eth.account.sign_transaction(tx, key)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            print(f'    tx: {tx_hash.hex()}')
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            if receipt['status'] == 1:
                print(f'    ✅ 成功')
                total_redeemed += size_total
            else:
                print(f'    ❌ 失败 (reverted)')
            time.sleep(2)
        except Exception as e:
            print(f'    ❌ 异常: {e}')

    print(f'\n赎回完成，估计回收: ${total_redeemed:.2f}')
    return total_redeemed

if __name__ == '__main__':
    redeem_all()
