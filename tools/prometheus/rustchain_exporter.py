#!/usr/bin/env python3
"""RustChain Prometheus exporter."""

import logging
import os
import time
from typing import Any

import requests
from prometheus_client import Gauge, start_http_server

NODE_URL = os.getenv("NODE_URL", "https://rustchain.org").rstrip("/")
EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9100"))
SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL", "60"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "15"))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("rustchain_exporter")

session = requests.Session()


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def fetch_json(endpoint: str) -> Any:
    url = f"{NODE_URL}{endpoint}"
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("request failed endpoint=%s error=%s", endpoint, exc)
        return None


rustchain_node_up = Gauge(
    "rustchain_node_up",
    "RustChain node health (1=up, 0=down)",
    labelnames=("version",),
)
rustchain_node_uptime_seconds = Gauge(
    "rustchain_node_uptime_seconds",
    "RustChain node uptime in seconds",
)
rustchain_active_miners_total = Gauge(
    "rustchain_active_miners_total",
    "Number of active miners",
)
rustchain_enrolled_miners_total = Gauge(
    "rustchain_enrolled_miners_total",
    "Number of enrolled miners",
)
rustchain_miner_last_attest_timestamp = Gauge(
    "rustchain_miner_last_attest_timestamp",
    "Unix timestamp of miner last attestation",
    labelnames=("miner", "arch"),
)
rustchain_current_epoch = Gauge("rustchain_current_epoch", "Current epoch")
rustchain_current_slot = Gauge("rustchain_current_slot", "Current slot")
rustchain_epoch_slot_progress = Gauge(
    "rustchain_epoch_slot_progress",
    "Progress inside current epoch from 0 to 1",
)
rustchain_epoch_seconds_remaining = Gauge(
    "rustchain_epoch_seconds_remaining",
    "Estimated seconds left until end of epoch",
)
rustchain_balance_rtc = Gauge(
    "rustchain_balance_rtc",
    "Miner balance in RTC",
    labelnames=("miner",),
)
rustchain_total_machines = Gauge(
    "rustchain_total_machines",
    "Total machines in hall of fame",
)
rustchain_total_attestations = Gauge(
    "rustchain_total_attestations",
    "Total attestations in hall of fame",
)
rustchain_oldest_machine_year = Gauge(
    "rustchain_oldest_machine_year",
    "Oldest machine manufacture year",
)
rustchain_highest_rust_score = Gauge(
    "rustchain_highest_rust_score",
    "Highest rust score in hall of fame",
)
rustchain_total_fees_collected_rtc = Gauge(
    "rustchain_total_fees_collected_rtc",
    "Total fees collected in RTC",
)
rustchain_fee_events_total = Gauge(
    "rustchain_fee_events_total",
    "Total fee events",
)


def collect_health() -> bool:
    payload = fetch_json("/health")
    if not isinstance(payload, dict):
        rustchain_node_up.clear()
        rustchain_node_up.labels(version="unknown").set(0)
        return False

    version = str(payload.get("version", "unknown"))
    ok_value = payload.get("ok", payload.get("healthy", True))
    is_up = 1 if bool(ok_value) else 0

    rustchain_node_up.clear()
    rustchain_node_up.labels(version=version).set(is_up)
    rustchain_node_uptime_seconds.set(
        _to_float(payload.get("uptime_s", payload.get("uptime_seconds", 0)))
    )
    return True


def collect_epoch() -> dict[str, int | float]:
    payload = fetch_json("/epoch")
    if not isinstance(payload, dict):
        return {
            "enrolled_miners": 0,
            "slot": 0,
            "slots_per_epoch": 0,
            "seconds_per_slot": 600,
        }

    epoch = _to_int(payload.get("epoch", payload.get("current_epoch", 0)))
    slot = _to_int(payload.get("slot", payload.get("current_slot", 0)))
    slots_per_epoch = _to_int(
        payload.get("slots_per_epoch", payload.get("blocks_per_epoch", 0))
    )
    seconds_per_slot = _to_float(
        payload.get("seconds_per_slot", payload.get("slot_duration_seconds", 600)),
        600,
    )

    rustchain_current_epoch.set(epoch)
    rustchain_current_slot.set(slot)

    if slots_per_epoch > 0:
        slot_in_epoch = slot % slots_per_epoch
        rustchain_epoch_slot_progress.set(slot_in_epoch / slots_per_epoch)
        rustchain_epoch_seconds_remaining.set(
            max(slots_per_epoch - slot_in_epoch, 0) * seconds_per_slot
        )
    else:
        rustchain_epoch_slot_progress.set(0)
        rustchain_epoch_seconds_remaining.set(0)

    return {
        "enrolled_miners": _to_int(payload.get("enrolled_miners", 0)),
        "slot": slot,
        "slots_per_epoch": slots_per_epoch,
        "seconds_per_slot": seconds_per_slot,
    }


def collect_miners(fallback_enrolled: int) -> None:
    payload = fetch_json("/api/miners")
    if not isinstance(payload, list):
        rustchain_active_miners_total.set(0)
        rustchain_enrolled_miners_total.set(fallback_enrolled)
        rustchain_miner_last_attest_timestamp.clear()
        return

    rustchain_miner_last_attest_timestamp.clear()

    now = time.time()
    active = 0
    for item in payload:
        if not isinstance(item, dict):
            continue
        miner = str(item.get("miner", item.get("id", "unknown")))
        arch = str(item.get("arch", item.get("device_arch", "unknown")))
        last_attest = _to_float(item.get("last_attest", item.get("last_attest_timestamp", 0)))
        rustchain_miner_last_attest_timestamp.labels(miner=miner, arch=arch).set(last_attest)
        if last_attest > 0 and (now - last_attest) <= 1800:
            active += 1

    rustchain_active_miners_total.set(active)
    rustchain_enrolled_miners_total.set(
        fallback_enrolled if fallback_enrolled > 0 else len(payload)
    )


def collect_hall_of_fame() -> None:
    payload = fetch_json("/api/hall_of_fame")
    if not isinstance(payload, dict):
        rustchain_total_machines.set(0)
        rustchain_total_attestations.set(0)
        rustchain_oldest_machine_year.set(0)
        rustchain_highest_rust_score.set(0)
        return

    stats = payload.get("stats", payload)
    if not isinstance(stats, dict):
        stats = {}

    rustchain_total_machines.set(_to_float(stats.get("total_machines", 0)))
    rustchain_total_attestations.set(_to_float(stats.get("total_attestations", 0)))
    rustchain_oldest_machine_year.set(
        _to_float(stats.get("oldest_machine_year", stats.get("oldest_year", 0)))
    )
    rustchain_highest_rust_score.set(_to_float(stats.get("highest_rust_score", 0)))


def collect_fee_pool() -> None:
    payload = fetch_json("/api/fee_pool")
    if not isinstance(payload, dict):
        rustchain_total_fees_collected_rtc.set(0)
        rustchain_fee_events_total.set(0)
        return

    rustchain_total_fees_collected_rtc.set(
        _to_float(payload.get("total_fees_collected_rtc", payload.get("total_fees", 0)))
    )
    rustchain_fee_events_total.set(
        _to_float(payload.get("fee_events_total", payload.get("total_fee_events", 0)))
    )


def collect_stats() -> None:
    payload = fetch_json("/api/stats")
    rustchain_balance_rtc.clear()

    if not isinstance(payload, dict):
        return

    balances = payload.get("balances")
    if not isinstance(balances, list):
        balances = payload.get("top_balances")

    if not isinstance(balances, list):
        return

    for row in balances:
        if not isinstance(row, dict):
            continue
        miner = str(row.get("miner", row.get("address", "unknown")))
        balance = _to_float(row.get("balance_rtc", row.get("balance", 0)))
        rustchain_balance_rtc.labels(miner=miner).set(balance)


def collect_once() -> None:
    health_ok = collect_health()
    epoch = collect_epoch()
    collect_miners(_to_int(epoch.get("enrolled_miners", 0)))
    collect_hall_of_fame()
    collect_fee_pool()
    collect_stats()
    logger.info("collection complete health_ok=%s", health_ok)


def main() -> None:
    logger.info(
        "starting exporter node_url=%s port=%s scrape_interval=%ss",
        NODE_URL,
        EXPORTER_PORT,
        SCRAPE_INTERVAL,
    )
    start_http_server(EXPORTER_PORT)

    while True:
        start = time.time()
        collect_once()
        elapsed = time.time() - start
        sleep_for = max(SCRAPE_INTERVAL - elapsed, 1)
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()
