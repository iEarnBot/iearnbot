#!/usr/bin/env python3
"""
USDC → USDC.e 自动兑换脚本（Polygon，Uniswap V3）
- 检测钱包 USDC native 余额
- 自动 approve + swap → USDC.e
- 滑点保护 0.5%，费率 100bps（最低滑点）

用法：
  python3 usdc_swap.py              # 兑换全部 USDC
  python3 usdc_swap.py --amount 50  # 兑换指定金额
  python3 usdc_swap.py --dry        # 模拟运行
"""

import argparse
import os
import sys
import time
from pathlib import Path

SKILL_DIR = Path.home() / '.openclaw/skills/polyclaw'
WORKSPACE = Path.home() / '.openclaw/workspace'
LOG_FILE  = WORKSPACE / 'polymarket_bot.log'

# 合约地址（Polygon mainnet）
USDC_NATIVE  = '0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359'
USDC_E       = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
SWAP_ROUTER  = '0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45'  # UniV3 SwapRouter02
QUOTER_V2    = '0x61fFE014bA17989E743c5F6cB21bF9697530B21e'
FEE_TIER     = 100      # 0.01% — 最低滑点
SLIPPAGE     = 0.005    # 0.5% 最大允许滑点
MIN_SWAP     = 1.0      # 最小兑换 $1

ERC20_ABI = [
    {"inputs":[{"name":"account","type":"address"}],"name":"balanceOf",
     "outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"decimals",
     "outputs":[{"name":"","type":"uint8"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],
     "name":"approve","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],
     "name":"allowance","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
]

QUOTER_ABI = [{"inputs":[{"components":[
    {"name":"tokenIn","type":"address"},{"name":"tokenOut","type":"address"},
    {"name":"amountIn","type":"uint256"},{"name":"fee","type":"uint24"},
    {"name":"sqrtPriceLimitX96","type":"uint160"}
],"name":"params","type":"tuple"}],
"name":"quoteExactInputSingle",
"outputs":[{"name":"amountOut","type":"uint256"},{"name":"sqrtPriceX96After","type":"uint160"},
           {"name":"initializedTicksCrossed","type":"uint32"},{"name":"gasEstimate","type":"uint256"}],
"stateMutability":"nonpayable","type":"function"}]

ROUTER_ABI = [{"inputs":[{"components":[
    {"name":"tokenIn","type":"address"},{"name":"tokenOut","type":"address"},
    {"name":"fee","type":"uint24"},{"name":"recipient","type":"address"},
    {"name":"amountIn","type":"uint256"},{"name":"amountOutMinimum","type":"uint256"},
    {"name":"sqrtPriceLimitX96","type":"uint160"}
],"name":"params","type":"tuple"}],
"name":"exactInputSingle",
"outputs":[{"name":"amountOut","type":"uint256"}],
"stateMutability":"payable","type":"function"}]


def log(msg):
    print(msg)
    with open(LOG_FILE, 'a') as f:
        from datetime import datetime
        f.write(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {msg}\n')


def swap_usdc_to_usdce(amount_override=None, dry_run=False):
    from web3 import Web3
    from eth_account import Account

    rpc = os.environ.get('CHAINSTACK_NODE', '')
    key = os.environ.get('POLYCLAW_PRIVATE_KEY', '')
    if not rpc or not key:
        # 从 .env 读取
        env_file = SKILL_DIR / '.env'
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if '=' in line:
                    k, _, v = line.partition('=')
                    k, v = k.strip(), v.strip()
                    if k == 'CHAINSTACK_NODE' and not rpc: rpc = v
                    if k == 'POLYCLAW_PRIVATE_KEY' and not key: key = v

    if not key.startswith('0x'):
        key = '0x' + key

    w3  = Web3(Web3.HTTPProvider(rpc))
    acc = Account.from_key(key)
    addr = Web3.to_checksum_address(acc.address)

    usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_NATIVE), abi=ERC20_ABI)
    bal  = usdc.functions.balanceOf(addr).call()
    bal_human = bal / 1e6

    log(f'[SWAP] USDC native 余额: ${bal_human:.4f}')

    if bal_human < MIN_SWAP:
        log(f'[SWAP] 余额 < ${MIN_SWAP}，无需兑换')
        return False

    # 兑换金额
    if amount_override:
        swap_amount = int(min(amount_override, bal_human) * 1e6)
    else:
        swap_amount = bal  # 全部

    swap_human = swap_amount / 1e6
    log(f'[SWAP] 准备兑换 ${swap_human:.4f} USDC → USDC.e')

    # 查询报价
    quoter = w3.eth.contract(address=Web3.to_checksum_address(QUOTER_V2), abi=QUOTER_ABI)
    try:
        quote = quoter.functions.quoteExactInputSingle({
            'tokenIn': Web3.to_checksum_address(USDC_NATIVE),
            'tokenOut': Web3.to_checksum_address(USDC_E),
            'amountIn': swap_amount,
            'fee': FEE_TIER,
            'sqrtPriceLimitX96': 0
        }).call()
        amount_out_expected = quote[0]
        amount_out_min = int(amount_out_expected * (1 - SLIPPAGE))
        log(f'[SWAP] 预计获得: ${amount_out_expected/1e6:.4f} USDC.e  最低保证: ${amount_out_min/1e6:.4f}')
    except Exception as e:
        log(f'[SWAP] 报价失败: {e}')
        return False

    if dry_run:
        log(f'[SWAP][DRY] 模拟完成，不实际执行')
        return True

    # 1. Approve USDC → SwapRouter
    allowance = usdc.functions.allowance(addr, Web3.to_checksum_address(SWAP_ROUTER)).call()
    if allowance < swap_amount:
        log(f'[SWAP] 授权 USDC → SwapRouter...')
        nonce = w3.eth.get_transaction_count(addr)
        approve_tx = usdc.functions.approve(
            Web3.to_checksum_address(SWAP_ROUTER),
            swap_amount * 10  # 授权10倍，减少未来重复授权
        ).build_transaction({
            'from': addr, 'nonce': nonce,
            'gas': 60000,
            'maxFeePerGas': w3.eth.gas_price * 2,
            'maxPriorityFeePerGas': Web3.to_wei(30, 'gwei'),
            'chainId': 137,
        })
        signed = w3.eth.account.sign_transaction(approve_tx, key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        log(f'[SWAP] Approve tx: {tx_hash.hex()}')
        w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        log(f'[SWAP] Approve 确认 ✅')
        time.sleep(2)

    # 2. Swap
    router = w3.eth.contract(address=Web3.to_checksum_address(SWAP_ROUTER), abi=ROUTER_ABI)
    nonce  = w3.eth.get_transaction_count(addr)
    deadline = int(time.time()) + 300  # 5分钟有效

    swap_tx = router.functions.exactInputSingle({
        'tokenIn':           Web3.to_checksum_address(USDC_NATIVE),
        'tokenOut':          Web3.to_checksum_address(USDC_E),
        'fee':               FEE_TIER,
        'recipient':         addr,
        'amountIn':          swap_amount,
        'amountOutMinimum':  amount_out_min,
        'sqrtPriceLimitX96': 0,
    }).build_transaction({
        'from': addr, 'nonce': nonce,
        'gas': 200000,
        'maxFeePerGas': w3.eth.gas_price * 2,
        'maxPriorityFeePerGas': Web3.to_wei(30, 'gwei'),
        'chainId': 137,
        'value': 0,
    })
    signed = w3.eth.account.sign_transaction(swap_tx, key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    log(f'[SWAP] Swap tx: {tx_hash.hex()}')

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt['status'] == 1:
        log(f'[SWAP] ✅ 兑换成功！${swap_human:.2f} USDC → USDC.e')
        return True
    else:
        log(f'[SWAP] ❌ 兑换失败，tx reverted')
        return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='USDC → USDC.e 自动兑换')
    parser.add_argument('--amount', type=float, help='兑换金额（默认全部）')
    parser.add_argument('--dry', action='store_true', help='模拟运行')
    args = parser.parse_args()
    swap_usdc_to_usdce(args.amount, args.dry)
