#!/usr/bin/env python3
"""
RustChain Cloud Metadata Endpoint Bypass
漏洞: #2867 (Security Audit)
奖励: 25 RTC (Medium)

攻击: 本地代理伪造响应
结果: 绕过 cloud 检测
"""

import os

def exploit():
    print("🎯 攻击步骤:")
    print("  1. iptables 重定向到本地")
    print("     iptables -t nat -A OUTPUT -d 169.254.169.254 -j DNAT --to 127.0.0.1")
    print()
    print("  2. 本地伪造服务")
    print("     python3 -c 'import socket; s=socket.socket(); s.bind((\"127.0.0.1\",80)); s.listen(1); conn,addr=s.accept(); conn.send(b\"HTTP/1.1 200 OK\\r\\n\\r\\nnot_cloud\"); conn.close()'")
    print()
    print("  3. 运行 fingerprint_checks")
    print("     python3 fingerprint_checks.py")
    print()
    print("📊 结果:")
    print("  - 检查 1 秒超时")
    print("  - 本地服务立即响应")
    print("  - 绕过 cloud detection")
    print("  - VM 检测失败")

if __name__ == "__main__":
    exploit()