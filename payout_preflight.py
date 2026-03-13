"""
payout_preflight.py — RustChain 支付预检验证模块
================================================

用途:
    验证钱包转账请求的 payload 格式，确保在发送到链上前数据有效
    
功能:
    - 管理员转账验证 (from_miner → to_miner)
    - 用户签名转账验证 (from_address → to_address，带 nonce 和签名)
    - 金额量化检查 (RTC → micro-units i64)
    - 钱包地址格式验证

集成方式:
    from payout_preflight import validate_wallet_transfer_admin, validate_wallet_transfer_signed
    
    # 验证管理员转账
    result = validate_wallet_transfer_admin(request.get_json())
    if not result.ok:
        return jsonify({"error": result.error}), 400
    
    # 验证用户签名转账
    result = validate_wallet_transfer_signed(request.get_json())
    if not result.ok:
        return jsonify({"error": result.error, "details": result.details}), 400

作者：Elyan Labs
日期：2026-03
"""

from __future__ import annotations

# Deployment-compat shim: some production environments run the node server as a
# single script (no package layout). Keep this module at repo root so
# `from payout_preflight import ...` works, while tests can still import it.

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class PreflightResult:
    """
    预检验证结果
    
    属性:
        ok: 验证是否通过
        error: 错误代码 (如果 ok=False)
        details: 验证通过的详细数据或错误上下文
    
    使用示例:
        result = validate_wallet_transfer_admin(payload)
        if result.ok:
            process_transfer(result.details)
        else:
            return error_response(result.error)
    """
    ok: bool
    error: str
    details: Dict[str, Any]


def _as_dict(payload: Any) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    将 payload 转换为字典
    
    参数:
        payload: 请求体数据 (可能是 dict 或其他类型)
    
    返回:
        Tuple[Optional[Dict], str]: (字典数据，错误代码)
        - 如果是 dict: 返回 (payload, "")
        - 如果不是 dict: 返回 (None, "invalid_json_body")
    
    为什么:
        - 统一处理 JSON 解析后的数据类型
        - 防止非 dict 数据导致后续代码崩溃
    """
    if not isinstance(payload, dict):
        return None, "invalid_json_body"
    return payload, ""


def _safe_float(v: Any) -> Tuple[Optional[float], str]:
    """
    安全地将值转换为 float
    
    参数:
        v: 任意类型的值
    
    返回:
        Tuple[Optional[float], str]: (浮点数值，错误代码)
        - 成功：返回 (float_value, "")
        - 失败：返回 (None, 错误代码)
    
    错误类型:
        - "amount_not_number": 无法转换为数字
        - "amount_not_finite": 数字是 inf 或 nan
    
    为什么:
        - 防止恶意输入导致崩溃 (如字符串、None、inf)
        - 统一错误处理，调用方只需检查错误代码
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None, "amount_not_number"
    if not math.isfinite(f):
        return None, "amount_not_finite"
    return f, ""


def validate_wallet_transfer_admin(payload: Any) -> PreflightResult:
    """
    验证管理员转账请求 (POST /wallet/transfer)
    
    用途:
        管理员从矿工钱包向另一个矿工钱包转账 (内部操作)
    
    请求格式:
        {
            "from_miner": "miner_wallet_1",
            "to_miner": "miner_wallet_2",
            "amount_rtc": 100.5
        }
    
    验证规则:
        1. from_miner 和 to_miner 必须存在且非空
        2. amount_rtc 必须是有效的正数
        3. 金额量化后必须 > 0 (最小单位 0.000001 RTC)
    
    参数字段说明:
        from_miner: 转出方矿工钱包地址
        to_miner: 转入方矿工钱包地址
        amount_rtc: 转账金额 (RTC 单位，支持小数)
    
    返回:
        PreflightResult: 验证结果
        - ok=True: details 包含验证通过的数据 (含量化后的 amount_i64)
        - ok=False: error 字段包含错误代码
    
    错误代码:
        - "invalid_json_body": payload 不是字典
        - "missing_from_or_to": 缺少 from_miner 或 to_miner
        - "amount_not_number": amount_rtc 无法转换为数字
        - "amount_not_finite": amount_rtc 是 inf 或 nan
        - "amount_must_be_positive": amount_rtc <= 0
        - "amount_too_small_after_quantization": 量化后为 0 (小于 0.000001 RTC)
    
    使用示例:
        result = validate_wallet_transfer_admin(request.get_json())
        if not result.ok:
            return jsonify({"error": result.error}), 400
        # result.details = {"from_miner": "...", "to_miner": "...", "amount_rtc": 100.5, "amount_i64": 100500000}
    """
    data, err = _as_dict(payload)
    if err:
        return PreflightResult(ok=False, error=err, details={})

    from_miner = data.get("from_miner")
    to_miner = data.get("to_miner")
    amount_rtc, aerr = _safe_float(data.get("amount_rtc", 0))

    if not from_miner or not to_miner:
        return PreflightResult(ok=False, error="missing_from_or_to", details={})
    if aerr:
        return PreflightResult(ok=False, error=aerr, details={})
    if amount_rtc is None or amount_rtc <= 0:
        return PreflightResult(ok=False, error="amount_must_be_positive", details={})
    amount_i64 = int(amount_rtc * 1_000_000)
    if amount_i64 <= 0:
        return PreflightResult(
            ok=False,
            error="amount_too_small_after_quantization",
            details={"amount_rtc": amount_rtc, "min_rtc": 0.000001},
        )

    return PreflightResult(
        ok=True,
        error="",
        details={
            "from_miner": str(from_miner),
            "to_miner": str(to_miner),
            "amount_rtc": amount_rtc,
            "amount_i64": amount_i64,
        },
    )


def validate_wallet_transfer_signed(payload: Any) -> PreflightResult:
    """
    验证用户签名转账请求 (POST /wallet/transfer/signed)
    
    用途:
        用户发起签名转账交易 (需要签名和公钥，用于链上验证)
    
    请求格式:
        {
            "from_address": "RTCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "to_address": "RTCyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
            "amount_rtc": 50.0,
            "nonce": 123,
            "signature": "0x...",
            "public_key": "0x..."
        }
    
    验证规则:
        1. 所有必填字段必须存在 (from_address, to_address, amount_rtc, nonce, signature, public_key)
        2. 地址格式必须是 RTC 开头，长度 43 字符
        3. from_address 和 to_address 不能相同
        4. amount_rtc 必须是有效的正数
        5. nonce 必须是正整数
    
    参数字段说明:
        from_address: 转出方地址 (RTC 开头，43 字符)
        to_address: 转入方地址 (RTC 开头，43 字符)
        amount_rtc: 转账金额 (RTC 单位)
        nonce: 交易序号 (防止重放攻击，必须 > 0)
        signature: 交易签名 (hex 字符串)
        public_key: 公钥 (用于验证签名)
    
    返回:
        PreflightResult: 验证结果
        - ok=True: details 包含验证通过的数据
        - ok=False: error 字段包含错误代码
    
    错误代码:
        - "invalid_json_body": payload 不是字典
        - "missing_required_fields": 缺少必填字段 (details 包含 missing 列表)
        - "amount_not_number": amount_rtc 无法转换为数字
        - "amount_not_finite": amount_rtc 是 inf 或 nan
        - "amount_must_be_positive": amount_rtc <= 0
        - "amount_too_small_after_quantization": 量化后为 0
        - "invalid_from_address_format": from_address 格式错误
        - "invalid_to_address_format": to_address 格式错误
        - "from_to_must_differ": 转账地址不能相同
        - "nonce_not_int": nonce 无法转换为整数
        - "nonce_must_be_gt_zero": nonce 必须 > 0
    
    地址格式说明:
        - RTC 主网地址：以 "RTC" 开头，总长度 43 字符
        - 示例：RTC4325af95d26d59c3ef025963656d22af638bb96b
    
    使用示例:
        result = validate_wallet_transfer_signed(request.get_json())
        if not result.ok:
            return jsonify({"error": result.error, "missing": result.details.get("missing")}), 400
        # result.details = {"from_address": "...", "to_address": "...", "amount_rtc": 50.0, "amount_i64": 50000000, "nonce": 123}
    """
    data, err = _as_dict(payload)
    if err:
        return PreflightResult(ok=False, error=err, details={})

    required = ["from_address", "to_address", "amount_rtc", "nonce", "signature", "public_key"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        return PreflightResult(ok=False, error="missing_required_fields", details={"missing": missing})

    from_address = str(data.get("from_address", "")).strip()
    to_address = str(data.get("to_address", "")).strip()
    amount_rtc, aerr = _safe_float(data.get("amount_rtc", 0))
    if aerr:
        return PreflightResult(ok=False, error=aerr, details={})
    if amount_rtc is None or amount_rtc <= 0:
        return PreflightResult(ok=False, error="amount_must_be_positive", details={})
    amount_i64 = int(amount_rtc * 1_000_000)
    if amount_i64 <= 0:
        return PreflightResult(
            ok=False,
            error="amount_too_small_after_quantization",
            details={"amount_rtc": amount_rtc, "min_rtc": 0.000001},
        )

    if not (from_address.startswith("RTC") and len(from_address) == 43):
        return PreflightResult(ok=False, error="invalid_from_address_format", details={})
    if not (to_address.startswith("RTC") and len(to_address) == 43):
        return PreflightResult(ok=False, error="invalid_to_address_format", details={})
    if from_address == to_address:
        return PreflightResult(ok=False, error="from_to_must_differ", details={})

    try:
        nonce_int = int(str(data.get("nonce")))
    except (TypeError, ValueError):
        return PreflightResult(ok=False, error="nonce_not_int", details={})
    if nonce_int <= 0:
        return PreflightResult(ok=False, error="nonce_must_be_gt_zero", details={})

    return PreflightResult(
        ok=True,
        error="",
        details={
            "from_address": from_address,
            "to_address": to_address,
            "amount_rtc": amount_rtc,
            "amount_i64": amount_i64,
            "nonce": nonce_int,
        },
    )

