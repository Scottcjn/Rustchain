#!/usr/bin/env python3
"""Enhanced RustChain Prometheus Exporter.

Provides deep observability into the RustChain network with per-miner
metrics, transaction throughput tracking, API latency histograms,
fee pool growth rate analysis, and attestation success rates.
"""

import logging
import os
import time
import threading
from collections import deque
from typing import Any

import requests
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Summary,
    start_http_server,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
NODE_URL = os.getenv("NODE_URL", "https://rustchain.org").rstrip("/")
EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9110"))
SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL", "30"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "15"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("rustchain_enhanced_exporter")

session = requests.Session()
session.headers.update({"User-Agent": "RustChain-Enhanced-Exporter/1.0"})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return default if value is None else float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return default if value is None else int(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# API latency histogram — tracks every outbound call to the node
# ---------------------------------------------------------------------------
API_LATENCY = Histogram(
    "rustchain_api_latency_seconds",
    "Latency of individual RustChain API requests",
    labelnames=("endpoint", "status"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

API_ERRORS = Counter(
    "rustchain_api_errors_total",
    "Total API request failures by endpoint",
    labelnames=("endpoint",),
)


def fetch_json(endpoint: str) -> Any:
    """Fetch JSON from the RustChain node and record latency."""
    url = f"{NODE_URL}{endpoint}"
    start = time.monotonic()
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        elapsed = time.monotonic() - start
        status = str(resp.status_code)
        API_LATENCY.labels(endpoint=endpoint, status=status).observe(elapsed)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError:
        return None
    except Exception as exc:
        elapsed = time.monotonic() - start
        API_LATENCY.labels(endpoint=endpoint, status="error").observe(elapsed)
        API_ERRORS.labels(endpoint=endpoint).inc()
        logger.warning("request failed endpoint=%s error=%s", endpoint, exc)
        return None


# ---------------------------------------------------------------------------
# Scrape-level metrics
# ---------------------------------------------------------------------------
SCRAPE_DURATION = Summary(
    "rustchain_scrape_duration_seconds",
    "Total time spent collecting all metrics per scrape cycle",
)

SCRAPE_ERRORS = Counter(
    "rustchain_scrape_errors_total",
    "Number of scrape cycles that encountered errors",
)

# ---------------------------------------------------------------------------
# Node health
# ---------------------------------------------------------------------------
NODE_UP = Gauge(
    "rustchain_node_up",
    "Node health (1=up, 0=down)",
    labelnames=("version",),
)
NODE_UPTIME = Gauge("rustchain_node_uptime_seconds", "Node uptime in seconds")
NODE_DB_STATUS = Gauge("rustchain_node_db_status", "DB read/write health (1=ok)")

# ---------------------------------------------------------------------------
# Epoch
# ---------------------------------------------------------------------------
CURRENT_EPOCH = Gauge("rustchain_current_epoch", "Current epoch number")
CURRENT_SLOT = Gauge("rustchain_current_slot", "Current slot number")
EPOCH_PROGRESS = Gauge(
    "rustchain_epoch_slot_progress",
    "Fraction of current epoch completed (0-1)",
)
EPOCH_SECONDS_REMAINING = Gauge(
    "rustchain_epoch_seconds_remaining",
    "Estimated seconds until epoch ends",
)
EPOCH_POT = Gauge("rustchain_epoch_pot_rtc", "Epoch reward pot in RTC")
ENROLLED_MINERS = Gauge("rustchain_enrolled_miners_total", "Enrolled miners")
TOTAL_SUPPLY = Gauge("rustchain_total_supply_rtc", "Total RTC supply")

# ---------------------------------------------------------------------------
# Per-miner metrics
# ---------------------------------------------------------------------------
MINER_BALANCE = Gauge(
    "rustchain_miner_balance_rtc",
    "Individual miner balance in RTC",
    labelnames=("miner", "arch", "hardware_type"),
)
MINER_ANTIQUITY = Gauge(
    "rustchain_miner_antiquity_multiplier",
    "Miner antiquity multiplier",
    labelnames=("miner", "arch"),
)
MINER_LAST_ATTEST = Gauge(
    "rustchain_miner_last_attest_timestamp",
    "Unix timestamp of miner last attestation",
    labelnames=("miner", "arch"),
)
MINER_RUST_SCORE = Gauge(
    "rustchain_miner_rust_score",
    "Individual miner rust score",
    labelnames=("miner",),
)
ACTIVE_MINERS = Gauge("rustchain_active_miners_total", "Active miners count")
MINERS_BY_HARDWARE = Gauge(
    "rustchain_miners_by_hardware",
    "Miners grouped by hardware type",
    labelnames=("hardware_type",),
)
MINERS_BY_ARCH = Gauge(
    "rustchain_miners_by_arch",
    "Miners grouped by CPU architecture",
    labelnames=("arch",),
)
AVG_ANTIQUITY = Gauge(
    "rustchain_avg_antiquity_multiplier",
    "Average antiquity multiplier across all miners",
)

# ---------------------------------------------------------------------------
# Attestation success rates
# ---------------------------------------------------------------------------
ATTESTATION_TOTAL = Gauge(
    "rustchain_attestations_total",
    "Total attestations observed",
)
ATTESTATION_SUCCESS = Gauge(
    "rustchain_attestations_successful",
    "Total successful attestations",
)
ATTESTATION_FAILED = Gauge(
    "rustchain_attestations_failed",
    "Total failed attestations",
)
ATTESTATION_SUCCESS_RATE = Gauge(
    "rustchain_attestation_success_rate",
    "Network-wide attestation success rate (0-1)",
)
MINER_ATTESTATION_SUCCESS_RATE = Gauge(
    "rustchain_miner_attestation_success_rate",
    "Per-miner attestation success rate (0-1)",
    labelnames=("miner",),
)

# ---------------------------------------------------------------------------
# Transaction throughput
# ---------------------------------------------------------------------------
TX_TOTAL = Gauge("rustchain_transactions_total", "Total transaction count")
TX_THROUGHPUT = Gauge(
    "rustchain_tx_throughput_per_second",
    "Transaction throughput (tx/s) computed over recent window",
)
TX_PENDING = Gauge("rustchain_tx_pending", "Pending transactions in mempool")
TX_AVG_FEE = Gauge(
    "rustchain_tx_avg_fee_rtc",
    "Average transaction fee in RTC",
)

# ---------------------------------------------------------------------------
# Fee pool & growth rate
# ---------------------------------------------------------------------------
FEE_POOL_TOTAL = Gauge(
    "rustchain_fee_pool_total_rtc",
    "Total fees collected in RTC",
)
FEE_EVENTS_TOTAL = Gauge(
    "rustchain_fee_events_total",
    "Total fee events",
)
FEE_POOL_GROWTH_RATE = Gauge(
    "rustchain_fee_pool_growth_rate_rtc_per_min",
    "Fee pool growth rate in RTC per minute",
)
FEE_POOL_EPOCH_DELTA = Gauge(
    "rustchain_fee_pool_epoch_delta_rtc",
    "Fee pool change within the current epoch",
)

# ---------------------------------------------------------------------------
# Hall of fame
# ---------------------------------------------------------------------------
HOF_MACHINES = Gauge("rustchain_hof_total_machines", "Total machines in hall of fame")
HOF_ATTESTATIONS = Gauge(
    "rustchain_hof_total_attestations",
    "Total attestations in hall of fame",
)
HOF_OLDEST_YEAR = Gauge(
    "rustchain_hof_oldest_machine_year",
    "Oldest machine manufacture year",
)
HOF_HIGHEST_RUST = Gauge(
    "rustchain_hof_highest_rust_score",
    "Highest rust score in hall of fame",
)

# ---------------------------------------------------------------------------
# Internal state for rate computations
# ---------------------------------------------------------------------------
_fee_samples: deque = deque(maxlen=60)
_tx_samples: deque = deque(maxlen=60)
_lock = threading.Lock()


# ===================================================================
# Collection functions
# ===================================================================

def collect_health() -> bool:
    payload = fetch_json("/health")
    if not isinstance(payload, dict):
        NODE_UP.clear()
        NODE_UP.labels(version="unknown").set(0)
        return False

    version = str(payload.get("version", "unknown"))
    ok_val = payload.get("ok", payload.get("healthy", True))
    NODE_UP.clear()
    NODE_UP.labels(version=version).set(1 if ok_val else 0)
    NODE_UPTIME.set(_to_float(payload.get("uptime_s", payload.get("uptime_seconds", 0))))
    NODE_DB_STATUS.set(1 if payload.get("db_rw", True) else 0)
    return True


def collect_epoch() -> dict:
    payload = fetch_json("/epoch")
    if not isinstance(payload, dict):
        return {"enrolled_miners": 0}

    epoch = _to_int(payload.get("epoch", payload.get("current_epoch", 0)))
    slot = _to_int(payload.get("slot", payload.get("current_slot", 0)))
    slots_per_epoch = _to_int(payload.get("slots_per_epoch", payload.get("blocks_per_epoch", 0)))
    seconds_per_slot = _to_float(
        payload.get("seconds_per_slot", payload.get("slot_duration_seconds", 600)), 600
    )

    CURRENT_EPOCH.set(epoch)
    CURRENT_SLOT.set(slot)
    EPOCH_POT.set(_to_float(payload.get("epoch_pot", 0)))
    ENROLLED_MINERS.set(_to_int(payload.get("enrolled_miners", 0)))
    TOTAL_SUPPLY.set(_to_float(payload.get("total_supply_rtc", 0)))

    if slots_per_epoch > 0:
        slot_in_epoch = slot % slots_per_epoch
        EPOCH_PROGRESS.set(slot_in_epoch / slots_per_epoch)
        EPOCH_SECONDS_REMAINING.set(max(slots_per_epoch - slot_in_epoch, 0) * seconds_per_slot)
    else:
        EPOCH_PROGRESS.set(0)
        EPOCH_SECONDS_REMAINING.set(0)

    return {"enrolled_miners": _to_int(payload.get("enrolled_miners", 0))}


def collect_miners(fallback_enrolled: int) -> None:
    payload = fetch_json("/api/miners")
    if not isinstance(payload, list):
        ACTIVE_MINERS.set(0)
        return

    MINER_LAST_ATTEST.clear()
    MINER_BALANCE.clear()
    MINER_ANTIQUITY.clear()
    MINER_RUST_SCORE.clear()
    MINERS_BY_HARDWARE.clear()
    MINERS_BY_ARCH.clear()
    MINER_ATTESTATION_SUCCESS_RATE.clear()

    now = time.time()
    active = 0
    hardware_counts: dict[str, int] = {}
    arch_counts: dict[str, int] = {}
    multipliers: list[float] = []

    for item in payload:
        if not isinstance(item, dict):
            continue

        miner = str(item.get("miner", item.get("id", "unknown")))
        arch = str(item.get("arch", item.get("device_arch", "unknown")))
        hw_type = str(item.get("hardware_type", "unknown"))
        last_attest = _to_float(item.get("last_attest", item.get("last_attest_timestamp", 0)))
        balance = _to_float(item.get("balance_rtc", item.get("balance", 0)))
        mult = _to_float(item.get("antiquity_multiplier", 1.0), 1.0)
        rust_score = _to_float(item.get("rust_score", 0))

        MINER_LAST_ATTEST.labels(miner=miner, arch=arch).set(last_attest)
        MINER_BALANCE.labels(miner=miner, arch=arch, hardware_type=hw_type).set(balance)
        MINER_ANTIQUITY.labels(miner=miner, arch=arch).set(mult)
        if rust_score > 0:
            MINER_RUST_SCORE.labels(miner=miner).set(rust_score)

        # Per-miner attestation success rate
        total_att = _to_int(item.get("total_attestations", 0))
        success_att = _to_int(item.get("successful_attestations", item.get("attestations_ok", 0)))
        if total_att > 0:
            MINER_ATTESTATION_SUCCESS_RATE.labels(miner=miner).set(success_att / total_att)

        hardware_counts[hw_type] = hardware_counts.get(hw_type, 0) + 1
        arch_counts[arch] = arch_counts.get(arch, 0) + 1
        multipliers.append(mult)

        if last_attest > 0 and (now - last_attest) <= 1800:
            active += 1

    for hw, count in hardware_counts.items():
        MINERS_BY_HARDWARE.labels(hardware_type=hw).set(count)
    for arch, count in arch_counts.items():
        MINERS_BY_ARCH.labels(arch=arch).set(count)

    ACTIVE_MINERS.set(active)
    if multipliers:
        AVG_ANTIQUITY.set(sum(multipliers) / len(multipliers))


def collect_attestation_stats() -> None:
    """Collect network-wide attestation metrics from /api/stats or /api/attestations."""
    payload = fetch_json("/api/stats")
    if not isinstance(payload, dict):
        return

    total = _to_int(payload.get("total_attestations", 0))
    success = _to_int(payload.get("successful_attestations", payload.get("attestations_ok", 0)))
    failed = _to_int(payload.get("failed_attestations", payload.get("attestations_failed", 0)))

    if total == 0 and success == 0 and failed == 0:
        # Try dedicated endpoint
        att_payload = fetch_json("/api/attestations")
        if isinstance(att_payload, dict):
            total = _to_int(att_payload.get("total", 0))
            success = _to_int(att_payload.get("successful", att_payload.get("ok", 0)))
            failed = _to_int(att_payload.get("failed", 0))

    ATTESTATION_TOTAL.set(total)
    ATTESTATION_SUCCESS.set(success)
    ATTESTATION_FAILED.set(failed)
    if total > 0:
        ATTESTATION_SUCCESS_RATE.set(success / total)
    else:
        ATTESTATION_SUCCESS_RATE.set(0)


def collect_transactions() -> None:
    """Collect transaction throughput metrics."""
    payload = fetch_json("/api/stats")
    if not isinstance(payload, dict):
        return

    tx_count = _to_int(payload.get("total_transactions", payload.get("tx_count", 0)))
    pending = _to_int(payload.get("pending_transactions", payload.get("mempool_size", 0)))
    avg_fee = _to_float(payload.get("avg_fee_rtc", payload.get("average_fee", 0)))

    TX_TOTAL.set(tx_count)
    TX_PENDING.set(pending)
    TX_AVG_FEE.set(avg_fee)

    # Compute throughput from sample window
    now = time.monotonic()
    with _lock:
        _tx_samples.append((now, tx_count))
        if len(_tx_samples) >= 2:
            oldest_time, oldest_count = _tx_samples[0]
            dt = now - oldest_time
            if dt > 0:
                TX_THROUGHPUT.set((tx_count - oldest_count) / dt)
        else:
            TX_THROUGHPUT.set(0)


def collect_fee_pool() -> None:
    """Collect fee pool metrics and compute growth rate."""
    payload = fetch_json("/api/fee_pool")
    if not isinstance(payload, dict):
        return

    total_fees = _to_float(
        payload.get("total_fees_collected_rtc", payload.get("total_fees", 0))
    )
    fee_events = _to_int(
        payload.get("fee_events_total", payload.get("total_fee_events", 0))
    )
    epoch_delta = _to_float(payload.get("epoch_delta_rtc", 0))

    FEE_POOL_TOTAL.set(total_fees)
    FEE_EVENTS_TOTAL.set(fee_events)
    FEE_POOL_EPOCH_DELTA.set(epoch_delta)

    # Compute growth rate (RTC per minute)
    now = time.monotonic()
    with _lock:
        _fee_samples.append((now, total_fees))
        if len(_fee_samples) >= 2:
            oldest_time, oldest_fees = _fee_samples[0]
            dt = now - oldest_time
            if dt > 0:
                rate_per_sec = (total_fees - oldest_fees) / dt
                FEE_POOL_GROWTH_RATE.set(rate_per_sec * 60.0)
        else:
            FEE_POOL_GROWTH_RATE.set(0)


def collect_hall_of_fame() -> None:
    payload = fetch_json("/api/hall_of_fame")
    if not isinstance(payload, dict):
        return

    stats = payload.get("stats", payload)
    if not isinstance(stats, dict):
        stats = {}

    HOF_MACHINES.set(_to_float(stats.get("total_machines", 0)))
    HOF_ATTESTATIONS.set(_to_float(stats.get("total_attestations", 0)))
    HOF_OLDEST_YEAR.set(_to_float(stats.get("oldest_machine_year", stats.get("oldest_year", 0))))
    HOF_HIGHEST_RUST.set(_to_float(stats.get("highest_rust_score", 0)))


# ===================================================================
# Main loop
# ===================================================================

@SCRAPE_DURATION.time()
def collect_once() -> None:
    """Run a full collection cycle."""
    try:
        health_ok = collect_health()
        epoch_info = collect_epoch()
        collect_miners(_to_int(epoch_info.get("enrolled_miners", 0)))
        collect_attestation_stats()
        collect_transactions()
        collect_fee_pool()
        collect_hall_of_fame()
        logger.info("collection complete health_ok=%s", health_ok)
    except Exception:
        SCRAPE_ERRORS.inc()
        logger.exception("scrape cycle failed")


def main() -> None:
    logger.info(
        "starting enhanced exporter node_url=%s port=%s interval=%ss",
        NODE_URL,
        EXPORTER_PORT,
        SCRAPE_INTERVAL,
    )
    start_http_server(EXPORTER_PORT)

    while True:
        start = time.monotonic()
        collect_once()
        elapsed = time.monotonic() - start
        sleep_for = max(SCRAPE_INTERVAL - elapsed, 1)
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()
