# SPDX-License-Identifier: MIT
import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "integrations" / "bottube_bridge.py"
spec = importlib.util.spec_from_file_location("bottube_bridge", MODULE_PATH)
bottube_bridge = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bottube_bridge
spec.loader.exec_module(bottube_bridge)


def test_plan_tip_rewards_accepts_raw_named_wallet_fields():
    config = dict(bottube_bridge.DEFAULT_CONFIG)
    config["max_rewards_per_wallet_per_day"] = 5
    state = {"paid": {}, "daily_counts": {}}
    full_wallet = "RTC" + ("a" * 40)
    tips = [
        {"id": "raw_named", "amount_rtc": "1.0", "wallet": "named_miner"},
        {"id": "raw_rtc_named", "amount_rtc": "1.0", "rtc_wallet": "miner:desk-01"},
        {"id": "memo_named", "amount_rtc": "1.0", "memo": "wallet: memo_miner"},
        {"id": "full_address", "amount_rtc": "1.0", "wallet": full_wallet},
    ]

    rewards = bottube_bridge.plan_tip_rewards(tips, config, state)

    wallets = {reward.key: reward.to_wallet for reward in rewards}
    assert wallets == {
        "tip:raw_named": "named_miner",
        "tip:raw_rtc_named": "miner:desk-01",
        "tip:memo_named": "memo_miner",
        "tip:full_address": full_wallet,
    }


def test_plan_tip_rewards_rejects_malformed_amounts():
    config = dict(bottube_bridge.DEFAULT_CONFIG)
    config["minimum_tip_rtc"] = 0.5
    config["max_rewards_per_wallet_per_day"] = 10
    state = {"paid": {}, "daily_counts": {}}
    tips = [
        {"id": "bool_true", "amount_rtc": True, "memo": "wallet: named_miner"},
        {"id": "bool_false", "amount_rtc": False, "memo": "wallet: named_miner"},
        {"id": "nan", "amount_rtc": "NaN", "memo": "wallet: named_miner"},
        {"id": "infinity", "amount_rtc": "Infinity", "memo": "wallet: named_miner"},
        {"id": "below_min", "amount_rtc": "0.1", "memo": "wallet: named_miner"},
        {"id": "valid", "amount_rtc": "1.0", "memo": "wallet: named_miner"},
    ]

    rewards = bottube_bridge.plan_tip_rewards(tips, config, state)

    assert [(reward.key, reward.amount_rtc) for reward in rewards] == [("tip:valid", 1.0)]
