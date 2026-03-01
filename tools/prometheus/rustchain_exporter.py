#!/usr/bin/env python3
"""
RustChain Prometheus Exporter
Scrapes RustChain node API and exposes metrics for Prometheus
"""

import os
import time
import logging
import requests
from prometheus_client import start_http_server, Gauge, Info, Counter
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings for self-signed certs
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Configuration
RUSTCHAIN_NODE_URL = os.getenv('RUSTCHAIN_NODE_URL', 'https://rustchain.org')
EXPORTER_PORT = int(os.getenv('EXPORTER_PORT', '9100'))
SCRAPE_INTERVAL = int(os.getenv('SCRAPE_INTERVAL', '60'))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('rustchain_exporter')

# Define Prometheus metrics
# Node health
node_up = Gauge('rustchain_node_up', 'Node is up and responding', ['version'])
node_uptime = Gauge('rustchain_node_uptime_seconds', 'Node uptime in seconds')
node_info = Info('rustchain_node', 'Node information')

# Miners
active_miners = Gauge('rustchain_active_miners_total', 'Number of active miners')
enrolled_miners = Gauge('rustchain_enrolled_miners_total', 'Number of enrolled miners')
miner_last_attest = Gauge('rustchain_miner_last_attest_timestamp', 
                          'Last attestation timestamp for miner',
                          ['miner', 'arch', 'device_family'])

# Epoch
current_epoch = Gauge('rustchain_current_epoch', 'Current epoch number')
current_slot = Gauge('rustchain_current_slot', 'Current slot number')
epoch_slot_progress = Gauge('rustchain_epoch_slot_progress', 'Epoch slot progress (0-1)')
epoch_seconds_remaining = Gauge('rustchain_epoch_seconds_remaining', 'Estimated seconds until next epoch')
epoch_pot = Gauge('rustchain_epoch_pot_rtc', 'Current epoch pot in RTC')
blocks_per_epoch = Gauge('rustchain_blocks_per_epoch', 'Blocks per epoch')

# Balances
miner_balance = Gauge('rustchain_balance_rtc', 'Miner balance in RTC', ['miner'])

# Hall of Fame
total_machines = Gauge('rustchain_total_machines', 'Total machines in Hall of Fame')
total_attestations = Gauge('rustchain_total_attestations', 'Total attestations across all machines')
oldest_machine_year = Gauge('rustchain_oldest_machine_year', 'Manufacture year of oldest machine')
highest_rust_score = Gauge('rustchain_highest_rust_score', 'Highest rust score in Hall of Fame')

# Fees (RIP-301)
total_fees_collected = Gauge('rustchain_total_fees_collected_rtc', 'Total fees collected in RTC')
fee_events_total = Gauge('rustchain_fee_events_total', 'Total number of fee events')

# Supply
total_supply = Gauge('rustchain_total_supply_rtc', 'Total RTC supply')


def fetch_json(endpoint):
    """Fetch JSON from RustChain API endpoint"""
    url = f"{RUSTCHAIN_NODE_URL}{endpoint}"
    try:
        response = requests.get(url, timeout=10, verify=False)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch {endpoint}: {e}")
        return None


def collect_health_metrics():
    """Collect node health metrics"""
    data = fetch_json('/health')
    if not data:
        node_up.labels(version='unknown').set(0)
        return
    
    version = data.get('version', 'unknown')
    node_up.labels(version=version).set(1 if data.get('ok') else 0)
    node_uptime.set(data.get('uptime_s', 0))
    
    node_info.info({
        'version': version,
        'db_rw': str(data.get('db_rw', False)),
        'tip_age_slots': str(data.get('tip_age_slots', 0))
    })
    
    logger.info(f"Health: version={version}, uptime={data.get('uptime_s')}s")


def collect_epoch_metrics():
    """Collect epoch metrics"""
    data = fetch_json('/epoch')
    if not data:
        return
    
    epoch = data.get('epoch', 0)
    slot = data.get('slot', 0)
    blocks = data.get('blocks_per_epoch', 144)
    
    current_epoch.set(epoch)
    current_slot.set(slot)
    blocks_per_epoch.set(blocks)
    epoch_pot.set(data.get('epoch_pot', 0))
    enrolled_miners.set(data.get('enrolled_miners', 0))
    total_supply.set(data.get('total_supply_rtc', 0))
    
    # Calculate progress and time remaining
    progress = slot / blocks if blocks > 0 else 0
    epoch_slot_progress.set(progress)
    
    # Estimate seconds remaining (assuming ~10 min per block)
    remaining_blocks = blocks - slot
    epoch_seconds_remaining.set(remaining_blocks * 600)
    
    logger.info(f"Epoch: {epoch}, Slot: {slot}/{blocks} ({progress:.1%})")


def collect_miner_metrics():
    """Collect miner metrics"""
    data = fetch_json('/api/miners')
    if not data or not isinstance(data, list):
        return
    
    active_count = 0
    for miner in data:
        miner_id = miner.get('miner', 'unknown')
        last_attest = miner.get('last_attest')
        arch = miner.get('device_arch', 'unknown')
        family = miner.get('device_family', 'unknown')
        
        if last_attest:
            miner_last_attest.labels(
                miner=miner_id,
                arch=arch,
                device_family=family
            ).set(last_attest)
            
            # Consider active if attested in last 30 minutes
            if time.time() - last_attest < 1800:
                active_count += 1
    
    active_miners.set(active_count)
    logger.info(f"Miners: {active_count} active, {len(data)} total")


def collect_balance_metrics():
    """Collect top miner balances"""
    data = fetch_json('/api/stats')
    if not data:
        return
    
    balances = data.get('top_balances', [])
    for entry in balances[:10]:  # Top 10 miners
        miner_id = entry.get('miner', 'unknown')
        balance = entry.get('balance', 0)
        miner_balance.labels(miner=miner_id).set(balance)
    
    logger.info(f"Balances: collected {len(balances[:10])} top miners")


def collect_hall_of_fame_metrics():
    """Collect Hall of Fame metrics"""
    data = fetch_json('/api/hall_of_fame')
    if not data or not isinstance(data, list):
        return
    
    total_machines.set(len(data))
    
    total_attests = sum(m.get('total_attestations', 0) for m in data)
    total_attestations.set(total_attests)
    
    years = [m.get('manufacture_year', 9999) for m in data if m.get('manufacture_year')]
    if years:
        oldest_machine_year.set(min(years))
    
    scores = [m.get('rust_score', 0) for m in data]
    if scores:
        highest_rust_score.set(max(scores))
    
    logger.info(f"Hall of Fame: {len(data)} machines, {total_attests} attestations")


def collect_fee_metrics():
    """Collect fee pool metrics (RIP-301)"""
    data = fetch_json('/api/fee_pool')
    if not data:
        return
    
    total_fees_collected.set(data.get('total_fees_collected_rtc', 0))
    fee_events_total.set(data.get('total_fee_events', 0))
    
    logger.info(f"Fees: {data.get('total_fees_collected_rtc', 0)} RTC collected, {data.get('total_fee_events', 0)} events")


def collect_all_metrics():
    """Collect all metrics from RustChain node"""
    logger.info("Starting metrics collection...")
    
    try:
        collect_health_metrics()
        collect_epoch_metrics()
        collect_miner_metrics()
        collect_balance_metrics()
        collect_hall_of_fame_metrics()
        collect_fee_metrics()
        
        logger.info("Metrics collection completed successfully")
    except Exception as e:
        logger.error(f"Error during metrics collection: {e}")


def main():
    """Main exporter loop"""
    logger.info(f"Starting RustChain Prometheus Exporter")
    logger.info(f"Node URL: {RUSTCHAIN_NODE_URL}")
    logger.info(f"Exporter port: {EXPORTER_PORT}")
    logger.info(f"Scrape interval: {SCRAPE_INTERVAL}s")
    
    # Start Prometheus HTTP server
    start_http_server(EXPORTER_PORT)
    logger.info(f"Metrics server started on :{EXPORTER_PORT}/metrics")
    
    # Initial collection
    collect_all_metrics()
    
    # Continuous collection loop
    while True:
        time.sleep(SCRAPE_INTERVAL)
        collect_all_metrics()


if __name__ == '__main__':
    main()
