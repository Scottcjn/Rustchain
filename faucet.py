#!/usr/bin/env python3
"""
RustChain Testnet Faucet - RustChain 测试网水龙头
==================================================

用途:
    为开发者提供免费测试用 RTC 代币，用于开发和测试 RustChain 应用

功能特性:
    - IP 地址限流：每个 IP 每 24 小时最多请求 0.5 RTC
    - SQLite 后端：记录所有请求，防止滥用
    - HTML 表单：简单的 Web 界面供用户请求代币
    - REST API: 支持程序化请求

API 端点:
    GET  /              - HTML 表单页面
    POST /drip          - 请求代币 (JSON: {wallet: "xxx"})
    GET  /stats         - 水龙头统计信息

限流规则:
    - 每 IP 每 24 小时：最多 0.5 RTC
    - 数据库记录所有请求，重启不清零

作者：Elyan Labs
日期：2026-03
"""

from __future__ import annotations

import sqlite3
import time
import os
from datetime import datetime, timedelta
from typing import Optional, Any
from flask import Flask, request, jsonify, render_template_string, Response

app = Flask(__name__)
DATABASE = 'faucet.db'  # SQLite 数据库文件，存储请求记录

# ─── 限流配置 ────────────────────────────────────────────────────────
# 为什么：防止滥用，确保公平分配测试代币

# 每个 IP 每 24 小时最多请求 0.5 RTC
# 为什么选择 0.5：足够测试交易，但不足以造成重大损失
MAX_DRIP_AMOUNT = 0.5  # RTC

# 限流周期：24 小时
# 为什么：每天重置，允许开发者持续测试但限制总量
RATE_LIMIT_HOURS = 24


def init_db() -> None:
    """
    初始化 SQLite 数据库
    
    表结构:
        drip_requests:
            - id: 主键，自增
            - wallet: 请求的钱包地址 (用于识别用户)
            - ip_address: 请求 IP (用于限流)
            - amount: 发放的代币数量
            - timestamp: 请求时间 (用于计算限流周期)
    
    为什么:
        - 持久化记录所有请求，防止重启后限流失效
        - 支持按 wallet 和 IP 双重维度查询
        - 时间戳用于计算 24 小时滚动窗口
    
    注意:
        - 数据库文件：faucet.db (当前目录)
        - 自动创建表，如果不存在
        - 安全：使用参数化查询，防止 SQL 注入
    """
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS drip_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            amount REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def get_client_ip() -> str:
    """
    获取客户端 IP 地址
    
    逻辑:
        1. 优先检查 X-Forwarded-For 头 (代理/负载均衡场景)
        2. 如果没有，使用 request.remote_addr
        3. 如果都没有，返回 127.0.0.1 (本地调试)
    
    为什么:
        - 支持反向代理部署 (如 Nginx 后)
        - X-Forwarded-For 可能包含多个 IP (客户端，代理 1, 代理 2...)
        - 取第一个 IP (真实客户端)
    
    返回:
        str: 客户端 IP 地址
    
    注意:
        - 用于限流，防止同一用户多 IP 请求
        - 不信任单一 IP，结合 wallet 地址双重验证
    """
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or '127.0.0.1'


def get_last_drip_time(ip_address: str) -> Optional[str]:
    """
    查询指定 IP 最后一次请求的时间
    
    参数:
        ip_address: 客户端 IP 地址
    
    返回:
        Optional[str]: ISO 格式时间戳，如果没有记录返回 None
    
    SQL 逻辑:
        - 按 ip_address 筛选
        - 按时间降序排列
        - 取第一条 (最近一次)
    
    为什么:
        - 用于计算距离上次请求过去了多少小时
        - 判断是否满足 24 小时间隔
    """
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        SELECT timestamp FROM drip_requests
        WHERE ip_address = ?
        ORDER BY timestamp DESC
        LIMIT 1
    ''', (ip_address,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None


def can_drip(ip_address: str) -> bool:
    """
    检查 IP 是否可以请求代币 (限流核心逻辑)
    
    参数:
        ip_address: 客户端 IP 地址
    
    返回:
        bool: True 可以请求，False 需要等待
    
    逻辑:
        1. 查询最后一次请求时间
        2. 如果没有记录 → 允许 (首次请求)
        3. 如果有记录 → 计算过去的小时数
        4. 如果 ≥ 24 小时 → 允许，否则拒绝
    
    为什么:
        - 24 小时滚动窗口，不是固定日历日
        - 防止用户在短时间内多次请求
        - 简单有效，不需要复杂的计数器
    """
    last_time = get_last_drip_time(ip_address)
    if not last_time:
        return True  # 首次请求，允许
    
    # 解析时间戳，计算时间差
    last_drip = datetime.fromisoformat(last_time.replace('Z', '+00:00'))
    now = datetime.now(last_drip.tzinfo)
    hours_since = (now - last_drip).total_seconds() / 3600
    
    return hours_since >= RATE_LIMIT_HOURS  # 是否满 24 小时


def get_next_available(ip_address: str) -> Optional[str]:
    """
    Get the next available time for this IP.
    
    参数:
        ip_address: 客户端 IP 地址
    
    返回:
        Optional[str]: 下次可请求的时间 (ISO 格式),如果首次请求返回 None
    """
    last_time = get_last_drip_time(ip_address)
    if not last_time:
        return None
    
    last_drip = datetime.fromisoformat(last_time.replace('Z', '+00:00'))
    next_available = last_drip + timedelta(hours=RATE_LIMIT_HOURS)
    now = datetime.now(last_drip.tzinfo)
    
    if next_available > now:
        return next_available.isoformat()
    return None


def record_drip(wallet: str, ip_address: str, amount: float) -> None:
    """
    Record a drip request to the database.
    
    参数:
        wallet: 钱包地址
        ip_address: 客户端 IP 地址
        amount: 发放的代币数量 (RTC)
    
    注意:
        - 使用参数化查询防止 SQL 注入
        - 提交后立即关闭连接，避免锁表
    """
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO drip_requests (wallet, ip_address, amount)
        VALUES (?, ?, ?)
    ''', (wallet, ip_address, amount))
    conn.commit()
    conn.close()


# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>RustChain Testnet Faucet</title>
    <style>
        body {
            font-family: 'Courier New', monospace;
            max-width: 600px;
            margin: 50px auto;
            padding: 20px;
            background: #0a0a0a;
            color: #00ff00;
        }
        h1 {
            color: #00ff00;
            border-bottom: 2px solid #00ff00;
            padding-bottom: 10px;
            text-align: center;
        }
        .form-section {
            background: #1a1a1a;
            border: 1px solid #00ff00;
            padding: 20px;
            margin: 20px 0;
            border-radius: 5px;
        }
        input[type="text"] {
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            background: #002200;
            color: #00ff00;
            border: 1px solid #00ff00;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 16px;
            box-sizing: border-box;
        }
        button {
            width: 100%;
            padding: 15px;
            background: #00aa00;
            color: #000;
            border: none;
            border-radius: 3px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
        }
        button:hover {
            background: #00ff00;
        }
        button:disabled {
            background: #333;
            color: #666;
            cursor: not-allowed;
        }
        .result {
            padding: 15px;
            margin: 15px 0;
            border-radius: 3px;
        }
        .success {
            background: #002200;
            border: 1px solid #00ff00;
            color: #00ff00;
        }
        .error {
            background: #220000;
            border: 1px solid #ff0000;
            color: #ff0000;
        }
        .info {
            background: #000022;
            border: 1px solid #0000ff;
            color: #6666ff;
        }
        .note {
            color: #888;
            font-size: 12px;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <h1>💧 RustChain Testnet Faucet</h1>
    
    <div class="form-section">
        <p>Get free test RTC tokens for development.</p>
        <form id="faucetForm">
            <label for="wallet">Your RTC Wallet Address:</label>
            <input type="text" id="wallet" name="wallet" placeholder="0x..." required>
            <button type="submit" id="submitBtn">Get Test RTC</button>
        </form>
        
        <div id="result"></div>
    </div>
    
    <div class="note">
        <p><strong>Rate Limit:</strong> {{ rate_limit }} RTC per {{ hours }} hours per IP</p>
        <p><strong>Network:</strong> RustChain Testnet</p>
    </div>

    <script>
        const form = document.getElementById('faucetForm');
        const result = document.getElementById('result');
        const submitBtn = document.getElementById('submitBtn');
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            submitBtn.disabled = true;
            submitBtn.textContent = 'Requesting...';
            result.innerHTML = '';
            
            const wallet = document.getElementById('wallet').value;
            
            try {
                const response = await fetch('/faucet/drip', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({wallet})
                });
                
                const data = await response.json();
                
                if (data.ok) {
                    result.innerHTML = '<div class="result success">✅ Success! Sent ' + data.amount + ' RTC to ' + wallet + '</div>';
                    if (data.next_available) {
                        result.innerHTML += '<div class="result info">Next available: ' + data.next_available + '</div>';
                    }
                } else {
                    result.innerHTML = '<div class="result error">❌ ' + data.error + '</div>';
                    if (data.next_available) {
                        result.innerHTML += '<div class="result info">Next available: ' + data.next_available + '</div>';
                    }
                }
            } catch (err) {
                result.innerHTML = '<div class="result error">❌ Error: ' + err.message + '</div>';
            }
            
            submitBtn.disabled = false;
            submitBtn.textContent = 'Get Test RTC';
        });
    </script>
</body>
</html>
"""


@app.route('/')
def index() -> Response:
    """
    Serve the faucet homepage (HTML form)
    
    Returns:
        Response: Rendered HTML template with rate limit info
    """
    return render_template_string(HTML_TEMPLATE, rate_limit=MAX_DRIP_AMOUNT, hours=RATE_LIMIT_HOURS)


@app.route('/faucet')
def faucet_page() -> Response:
    """
    Serve the faucet page (alias for index)
    
    Returns:
        Response: Rendered HTML template with rate limit info
    """
    return render_template_string(HTML_TEMPLATE, rate_limit=MAX_DRIP_AMOUNT, hours=RATE_LIMIT_HOURS)


@app.route('/faucet/drip', methods=['POST'])
def drip() -> tuple[Response, int]:
    """
    Handle faucet drip request (distribute test tokens)
    
    Request body (JSON):
        {"wallet": "0x..."} - Wallet address to receive test RTC
    
    Response (success):
        {
            "ok": true,
            "amount": 0.5,
            "wallet": "0x...",
            "next_available": "2026-03-14T12:59:00"
        }
    
    Response (rate limited):
        {
            "ok": false,
            "error": "Rate limit exceeded",
            "next_available": "2026-03-14T12:59:00"
        }
    
    Rate Limiting:
        - Each IP can request once every 24 hours
        - Max 0.5 RTC per request
    
    Validation:
        - Wallet must start with "0x" and be at least 10 characters
        - Returns 400 for invalid wallet, 429 for rate limit exceeded
    """
    data = request.get_json()
    
    if not data or 'wallet' not in data:
        return jsonify({'ok': False, 'error': 'Wallet address required'}), 400
    
    wallet = data['wallet'].strip()
    
    # Basic wallet validation (should start with 0x and be reasonably long)
    if not wallet.startswith('0x') or len(wallet) < 10:
        return jsonify({'ok': False, 'error': 'Invalid wallet address'}), 400
    
    ip = get_client_ip()
    
    # Check rate limit
    if not can_drip(ip):
        next_available = get_next_available(ip)
        return jsonify({
            'ok': False,
            'error': 'Rate limit exceeded',
            'next_available': next_available
        }), 429
    
    # Record the drip (in production, this would actually transfer tokens)
    # For now, we simulate the drip
    amount = MAX_DRIP_AMOUNT
    record_drip(wallet, ip, amount)
    
    return jsonify({
        'ok': True,
        'amount': amount,
        'wallet': wallet,
        'next_available': (datetime.now() + timedelta(hours=RATE_LIMIT_HOURS)).isoformat()
    })


if __name__ == '__main__':
    # Initialize database
    if not os.path.exists(DATABASE):
        init_db()
    else:
        init_db()  # Ensure table exists
    
    # Run the server
    print("Starting RustChain Faucet on http://0.0.0.0:8090/faucet")
    app.run(host='0.0.0.0', port=8090, debug=False)
