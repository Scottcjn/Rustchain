#!/usr/bin/env python3
"""BoTTube -> RustChain reward bridge.

The bridge polls public BoTTube endpoints, finds creator RTC wallets, and
queues RustChain transfers for content rewards, milestones, and tips. It is
idempotent by design: every reward has a stable key recorded in a local state
file before the next polling pass can pay it again.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "bottube_api_base": "https://bottube.ai",
    "rustchain_node_url": "https://50.28.86.131",
    "rustchain_from_wallet": "founder_team_bounty",
    "admin_key_env": "RTC_ADMIN_KEY",
    "bottube_api_key_env": "BOTTUBE_API_KEY",
    "state_file": "bottube_bridge_state.json",
    "dry_run": True,
    "poll_interval_seconds": 300,
    "min_video_length_seconds": 6,
    "max_rewards_per_creator_per_day": 3,
    "max_rewards_per_wallet_per_day": 3,
    "wallet_pattern": r"\b(RTC[a-fA-F0-9]{40})\b",
    "upload_reward_rtc": 0.25,
    "view_milestone_reward_rtc": 0.5,
    "subscriber_milestone_reward_rtc": 1.0,
    "minimum_tip_rtc": 0.001,
    "view_milestones": [100, 1000, 10000],
    "subscriber_milestones": [10, 100, 1000],
    "max_items_per_poll": 50,
}


@dataclass
class Reward:
    key: str
    to_wallet: str
    amount_rtc: float
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BridgeError(RuntimeError):
    pass


def load_config(path: Path) -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            config.update(json.load(fh))
    return config


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"paid": {}, "daily_counts": {}}
    with path.open("r", encoding="utf-8") as fh:
        state = json.load(fh)
    state.setdefault("paid", {})
    state.setdefault("daily_counts", {})
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
        fh.write("\n")
    tmp.replace(path)


def request_json(
    method: str,
    url: str,
    *,
    api_key: str | None = None,
    admin_key: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> Any:
    headers = {"Accept": "application/json"}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["X-API-Key"] = api_key
    if admin_key:
        headers["X-Admin-Key"] = admin_key
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise BridgeError(f"{method} {url} failed: {exc.code} {details}") from exc
    except urllib.error.URLError as exc:
        raise BridgeError(f"{method} {url} failed: {exc.reason}") from exc
    return json.loads(raw) if raw else {}


def normalize_base(url: str) -> str:
    return str(url).strip().rstrip("/")


def extract_items(payload: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def fetch_videos(config: dict[str, Any], api_key: str | None) -> list[dict[str, Any]]:
    base = normalize_base(config["bottube_api_base"])
    limit = int(config["max_items_per_poll"])
    candidates = [
        f"{base}/api/videos?limit={limit}",
        f"{base}/api/feed?limit={limit}",
        f"{base}/api/trending?limit={limit}",
    ]
    for url in candidates:
        try:
            payload = request_json("GET", url, api_key=api_key)
        except BridgeError:
            continue
        videos = extract_items(payload, ("videos", "items", "feed", "results"))
        if videos:
            return videos[:limit]
    return []


def fetch_agent(config: dict[str, Any], api_key: str | None, name: str) -> dict[str, Any]:
    if not name:
        return {}
    base = normalize_base(config["bottube_api_base"])
    safe_name = urllib.parse.quote(name, safe="")
    try:
        payload = request_json("GET", f"{base}/api/agents/{safe_name}", api_key=api_key)
    except BridgeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def fetch_tips(config: dict[str, Any], api_key: str | None) -> list[dict[str, Any]]:
    if not api_key:
        return []
    base = normalize_base(config["bottube_api_base"])
    try:
        payload = request_json("GET", f"{base}/api/agents/me/earnings", api_key=api_key)
    except BridgeError:
        return []
    return extract_items(payload, ("tips", "earnings", "items", "transactions"))


def raw_wallet(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"RTC[a-fA-F0-9]{40}", text):
        return text
    # Raw wallet fields may use a named miner wallet instead of an RTC address.
    if re.fullmatch(r"[A-Za-z0-9_.:-]{3,96}", text):
        return text
    return None


def wallet_from_text(text: str, pattern: str) -> str | None:
    if not text:
        return None
    explicit = re.search(
        r"(?:RTC\s*)?(?:wallet|payout|address)\s*[:=]\s*`?([A-Za-z0-9_.:-]{3,96})`?",
        text,
        re.IGNORECASE,
    )
    if explicit:
        return explicit.group(1).strip("` ,.;)")
    # Free text is only allowed to contain full RTC addresses. This avoids
    # treating ordinary title words such as "Episode" or "Preview" as wallets.
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip("` ,.;)")
    return None


def resolve_wallet(video: dict[str, Any], agent: dict[str, Any], config: dict[str, Any]) -> str | None:
    pattern = str(config["wallet_pattern"])
    raw_fields = [
        video.get("rtc_wallet"),
        video.get("wallet"),
        video.get("payout_wallet"),
        agent.get("rtc_wallet"),
        agent.get("wallet"),
        agent.get("payout_wallet"),
    ]
    for value in raw_fields:
        wallet = raw_wallet(value)
        if wallet:
            return wallet

    text_fields = [
        video.get("description"),
        video.get("title"),
        agent.get("bio"),
        agent.get("description"),
    ]
    for value in text_fields:
        wallet = wallet_from_text(str(value or ""), pattern)
        if wallet:
            return wallet
    return None


def video_id(video: dict[str, Any]) -> str:
    for key in ("id", "video_id", "slug", "uuid"):
        if video.get(key) is not None:
            return str(video[key])
    raise BridgeError(f"video missing ID: {video}")


def video_creator(video: dict[str, Any]) -> str:
    for key in ("agent_name", "agent", "creator", "creator_name", "username"):
        if video.get(key):
            value = video[key]
            if isinstance(value, dict):
                return str(value.get("name") or value.get("agent_name") or "")
            return str(value)
    return ""


def video_duration(video: dict[str, Any]) -> float:
    for key in ("duration", "duration_seconds", "length_seconds"):
        try:
            return float(video.get(key) or 0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def video_views(video: dict[str, Any]) -> int:
    for key in ("views", "view_count", "plays"):
        try:
            return int(video.get(key) or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def agent_subscribers(agent: dict[str, Any]) -> int:
    for key in ("subscribers", "subscriber_count", "followers"):
        try:
            return int(agent.get(key) or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def today_key() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def within_daily_limit(state: dict[str, Any], creator: str, limit: int) -> bool:
    if not creator:
        return True
    day = today_key()
    counts = state.setdefault("daily_counts", {}).setdefault(day, {})
    return int(counts.get(creator, 0)) < limit


def increment_daily_limit(state: dict[str, Any], creator: str) -> None:
    if not creator:
        return
    day = today_key()
    counts = state.setdefault("daily_counts", {}).setdefault(day, {})
    counts[creator] = int(counts.get(creator, 0)) + 1
    for old_day in list(state.get("daily_counts", {})):
        if old_day != day:
            state["daily_counts"].pop(old_day, None)


def plan_video_rewards(
    videos: list[dict[str, Any]],
    config: dict[str, Any],
    state: dict[str, Any],
    api_key: str | None,
) -> list[Reward]:
    rewards: list[Reward] = []
    paid = state.setdefault("paid", {})
    min_duration = float(config["min_video_length_seconds"])
    creator_daily_limit = int(config["max_rewards_per_creator_per_day"])
    wallet_daily_limit = int(config["max_rewards_per_wallet_per_day"])
    planned_counts: dict[str, int] = {}

    def count_key(prefix: str, value: str) -> str:
        return f"{prefix}:{value}" if value else ""

    def can_plan(creator: str, wallet: str) -> bool:
        keys = [
            (count_key("creator", creator), creator_daily_limit),
            (count_key("wallet", wallet), wallet_daily_limit),
        ]
        day_counts = state.setdefault("daily_counts", {}).setdefault(today_key(), {})
        for key, limit in keys:
            if not key:
                continue
            if not within_daily_limit(state, key, limit):
                return False
            already = int(day_counts.get(key, 0))
            if already + planned_counts.get(key, 0) >= limit:
                return False
        return True

    def add_reward(reward: Reward) -> None:
        creator = str(reward.metadata.get("creator") or "")
        wallet = reward.to_wallet
        rewards.append(reward)
        for key in (count_key("creator", creator), count_key("wallet", wallet)):
            if key:
                planned_counts[key] = planned_counts.get(key, 0) + 1

    for video in videos:
        vid = video_id(video)
        creator = video_creator(video)
        agent = fetch_agent(config, api_key, creator)
        wallet = resolve_wallet(video, agent, config)
        if not wallet:
            continue
        if video_duration(video) and video_duration(video) < min_duration:
            continue
        if not can_plan(creator, wallet):
            continue

        upload_key = f"upload:{vid}"
        if upload_key not in paid:
            add_reward(
                Reward(
                    key=upload_key,
                    to_wallet=wallet,
                    amount_rtc=float(config["upload_reward_rtc"]),
                    reason=f"bottube_upload:{vid}",
                    metadata={"video_id": vid, "creator": creator},
                )
            )

        views = video_views(video)
        for milestone in config["view_milestones"]:
            key = f"views:{vid}:{milestone}"
            if views >= int(milestone) and key not in paid and can_plan(creator, wallet):
                add_reward(
                    Reward(
                        key=key,
                        to_wallet=wallet,
                        amount_rtc=float(config["view_milestone_reward_rtc"]),
                        reason=f"bottube_views:{vid}:{milestone}",
                        metadata={"video_id": vid, "creator": creator, "views": views},
                    )
                )

        subs = agent_subscribers(agent)
        for milestone in config["subscriber_milestones"]:
            key = f"subscribers:{creator}:{milestone}"
            if creator and subs >= int(milestone) and key not in paid and can_plan(creator, wallet):
                add_reward(
                    Reward(
                        key=key,
                        to_wallet=wallet,
                        amount_rtc=float(config["subscriber_milestone_reward_rtc"]),
                        reason=f"bottube_subscribers:{creator}:{milestone}",
                        metadata={"creator": creator, "subscribers": subs},
                    )
                )

    return rewards


def plan_tip_rewards(tips: list[dict[str, Any]], config: dict[str, Any], state: dict[str, Any]) -> list[Reward]:
    rewards: list[Reward] = []
    paid = state.setdefault("paid", {})
    minimum = float(config["minimum_tip_rtc"])
    pattern = str(config["wallet_pattern"])
    for tip in tips:
        tip_id = str(tip.get("id") or tip.get("tx_id") or tip.get("created_at") or "")
        if not tip_id:
            continue
        key = f"tip:{tip_id}"
        if key in paid:
            continue
        try:
            amount = float(tip.get("amount_rtc") or tip.get("amount") or 0)
        except (TypeError, ValueError):
            continue
        if amount < minimum:
            continue
        wallet = (
            wallet_from_text(str(tip.get("rtc_wallet") or tip.get("wallet") or ""), pattern)
            or wallet_from_text(str(tip.get("memo") or tip.get("note") or ""), pattern)
        )
        if not wallet:
            continue
        rewards.append(
            Reward(
                key=key,
                to_wallet=wallet,
                amount_rtc=amount,
                reason=f"bottube_tip:{tip_id}",
                metadata={"tip_id": tip_id},
            )
        )
    return rewards


def send_reward(config: dict[str, Any], admin_key: str | None, reward: Reward) -> dict[str, Any]:
    if config.get("dry_run", True):
        print(f"DRY RUN {reward.amount_rtc} RTC -> {reward.to_wallet} ({reward.reason})")
        return {"ok": True, "dry_run": True}
    if not admin_key:
        raise BridgeError("RTC admin key is required when dry_run is false")
    base = normalize_base(config["rustchain_node_url"])
    return request_json(
        "POST",
        f"{base}/wallet/transfer",
        admin_key=admin_key,
        payload={
            "from_miner": config["rustchain_from_wallet"],
            "to_miner": reward.to_wallet,
            "amount_rtc": reward.amount_rtc,
            "reason": reward.reason,
        },
    )


def mark_paid(state: dict[str, Any], reward: Reward, result: dict[str, Any]) -> None:
    state.setdefault("paid", {})[reward.key] = {
        "wallet": reward.to_wallet,
        "amount_rtc": reward.amount_rtc,
        "reason": reward.reason,
        "metadata": reward.metadata,
        "result": result,
        "paid_at": int(time.time()),
    }
    creator = str(reward.metadata.get("creator") or "")
    if creator:
        increment_daily_limit(state, f"creator:{creator}")
    increment_daily_limit(state, f"wallet:{reward.to_wallet}")


def run_once(config: dict[str, Any]) -> int:
    state_path = Path(config["state_file"])
    state = load_state(state_path)
    admin_key = os.environ.get(str(config["admin_key_env"]), "")
    api_key = os.environ.get(str(config["bottube_api_key_env"]), "")

    videos = fetch_videos(config, api_key)
    rewards = plan_video_rewards(videos, config, state, api_key)
    rewards.extend(plan_tip_rewards(fetch_tips(config, api_key), config, state))

    completed = 0
    for reward in rewards:
        if reward.key in state.get("paid", {}):
            continue
        result = send_reward(config, admin_key, reward)
        if config.get("dry_run", True):
            completed += 1
            continue
        mark_paid(state, reward, result)
        save_state(state_path, state)
        completed += 1
    return completed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Bridge BoTTube rewards to RustChain RTC transfers.")
    parser.add_argument("--config", default="bottube_bridge.example.json", help="Path to JSON config")
    parser.add_argument("--once", action="store_true", help="Run one polling pass and exit")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run mode for this process")
    args = parser.parse_args(argv)

    config = load_config(Path(args.config))
    if args.dry_run:
        config["dry_run"] = True

    if args.once:
        count = run_once(config)
        print(f"completed_rewards={count}")
        return 0

    interval = int(config["poll_interval_seconds"])
    while True:
        try:
            count = run_once(config)
            print(f"completed_rewards={count}")
        except Exception as exc:  # noqa: BLE001 - daemon logs and keeps polling.
            print(f"bridge_error={exc}", file=sys.stderr)
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
