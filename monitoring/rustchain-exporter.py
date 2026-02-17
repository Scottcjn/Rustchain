#!/usr/bin/env python3
"""
RustChain Prometheus Exporter
Exposes RustChain node metrics in Prometheus format
"""
import time
import os
import requests
from prometheus_client import start_http_server, Gauge, Counter, Info
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('rustchain-exporter')

# Configuration
RUSTCHAIN_NODE = os.environ.get('RUSTCHAIN_NODE', 'https://50.28.86.131')
EXPORTER_PORT = int(os.environ.get('EXPORTER_PORT', 9100))
SCRAPE_INTERVAL = int(os.environ.get('SCRAPE_INTERVAL', 30))  # seconds
TLS_VERIFY = os.environ.get('TLS_VERIFY', 'true').lower() in ('true', '1', 'yes')
TLS_CA_BUNDLE = os.environ.get('TLS_CA_BUNDLE', None)  # Optional CA cert path

# Prometheus metrics
node_health = Gauge('rustchain_node_health', 'Node health status (1=healthy, 0=unhealthy)')
node_uptime_seconds = Gauge('rustchain_node_uptime_seconds', 'Node uptime in seconds')
node_db_status = Gauge('rustchain_node_db_status', 'Database read/write status (1=ok, 0=error)')
node_version = Info('rustchain_node_version', 'Node version information')

epoch_number = Gauge('rustchain_epoch_number', 'Current epoch number')
epoch_slot = Gauge('rustchain_epoch_slot', 'Current slot in epoch')
epoch_pot = Gauge('rustchain_epoch_pot', 'Epoch pot size in RTC')
enrolled_miners = Gauge('rustchain_enrolled_miners', 'Number of enrolled miners')
total_supply = Gauge('rustchain_total_supply_rtc', 'Total RTC supply')

active_miners = Gauge('rustchain_active_miners', 'Number of active miners')
miners_by_hardware = Gauge('rustchain_miners_by_hardware', 'Miners grouped by hardware type', ['hardware_type'])
miners_by_arch = Gauge('rustchain_miners_by_arch', 'Miners grouped by architecture', ['arch'])
avg_antiquity_multiplier = Gauge('rustchain_avg_antiquity_multiplier', 'Average antiquity multiplier')

scrape_errors = Counter('rustchain_scrape_errors_total', 'Total number of scrape errors')
scrape_duration_seconds = Gauge('rustchain_scrape_duration_seconds', 'Duration of last scrape')


def fetch_json(endpoint):
    """Fetch JSON data from RustChain node API"""
    try:
        url = f"{RUSTCHAIN_NODE}{endpoint}"
        # Determine verification behavior
        verify = TLS_VERIFY
        if TLS_CA_BUNDLE:
            verify = TLS_CA_BUNDLE
        
        response = requests.get(url, verify=verify, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching {endpoint}: {e}")
        scrape_errors.inc()
        return None


def collect_metrics():
    """Collect all metrics from RustChain node"""
    start_time = time.time()
    
    try:
        # Health metrics
        health = fetch_json('/health')
        if health:
            node_health.set(1 if health.get('ok') else 0)
            node_uptime_seconds.set(health.get('uptime_s', 0))
            node_db_status.set(1 if health.get('db_rw') else 0)
            node_version.info({'version': health.get('version', 'unknown')})
        
        # Epoch metrics
        epoch = fetch_json('/epoch')
        if epoch:
            epoch_number.set(epoch.get('epoch', 0))
            epoch_slot.set(epoch.get('slot', 0))
            epoch_pot.set(epoch.get('epoch_pot', 0))
            enrolled_miners.set(epoch.get('enrolled_miners', 0))
            total_supply.set(epoch.get('total_supply_rtc', 0))
        
        # Miner metrics
        miners = fetch_json('/api/miners')
        if miners:
            active_miners.set(len(miners))
            
            # Group by hardware type
            hardware_counts = {}
            arch_counts = {}
            multipliers = []
            
            for miner in miners:
                hw_type = miner.get('hardware_type', 'Unknown')
                arch = miner.get('device_arch', 'Unknown')
                mult = miner.get('antiquity_multiplier', 1.0)
                
                hardware_counts[hw_type] = hardware_counts.get(hw_type, 0) + 1
                arch_counts[arch] = arch_counts.get(arch, 0) + 1
                multipliers.append(mult)
            
            # Update Prometheus metrics
            for hw_type, count in hardware_counts.items():
                miners_by_hardware.labels(hardware_type=hw_type).set(count)
            
            for arch, count in arch_counts.items():
                miners_by_arch.labels(arch=arch).set(count)
            
            if multipliers:
                avg_antiquity_multiplier.set(sum(multipliers) / len(multipliers))
        
        # Record scrape duration
        duration = time.time() - start_time
        scrape_duration_seconds.set(duration)
        logger.info(f"Metrics collected in {duration:.2f}s")
        
    except Exception as e:
        logger.error(f"Error collecting metrics: {e}")
        scrape_errors.inc()


def main():
    """Main exporter loop"""
    logger.info(f"Starting RustChain Prometheus Exporter on port {EXPORTER_PORT}")
    logger.info(f"Scraping {RUSTCHAIN_NODE} every {SCRAPE_INTERVAL} seconds")
    
    # Start HTTP server for Prometheus to scrape
    start_http_server(EXPORTER_PORT)
    
    # Continuous collection loop
    while True:
        collect_metrics()
        time.sleep(SCRAPE_INTERVAL)


if __name__ == '__main__':
    main()
