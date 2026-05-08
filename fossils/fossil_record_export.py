#!/usr/bin/env python3
"""
The Fossil Record — Attestation Archaeology Data Export

Exports attestation history from RustChain database for visualization.
Can be used as:
1. Standalone script to generate JSON/CSV exports
2. API endpoint handler for the visualizer
3. Sample data generator for demonstration

Usage:
    python3 fossil_record_export.py --export attestation_history.json
    python3 fossil_record_export.py --sample --output sample_data.json
    python3 fossil_record_export.py --serve  # Start HTTP server
"""

import os
import sys
import json
import sqlite3
import argparse
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from http.server import HTTPServer, SimpleHTTPRequestHandler
from functools import lru_cache

# Canonical genesis timestamp — must match node consensus modules
GENESIS_TIMESTAMP = 1764706927  # Production chain launch (Dec 2, 2025)

logging.basicConfig(
    level=logging.INFO,
    format='[Fossil Record] %(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

# Default database paths to check
DEFAULT_DB_PATHS = [
    os.getenv('RUSTCHAIN_DB_PATH', 'rustchain.db'),
    'node/rustchain_v2.db',
    '../rustchain/rustchain_v2.db',
    '/root/rustchain/rustchain_v2.db',
    'rustchain_v2_integrated_v2.2.1_rip200.db',
]

# Architecture mapping for normalization
ARCH_MAPPING = {
    'PowerPC': 'ppc64le',
    'ppc64le': 'ppc64le',
    'POWER8': 'POWER8',
    'G4': 'G4',
    'G5': 'G5',
    'G3': 'G3',
    'x86_64': 'x86_64',
    'AMD64': 'x86_64',
    'ARM': 'ARM',
    'ARM64': 'ARM',
    'aarch64': 'ARM',
    'Apple Silicon': 'Apple Silicon',
    'M1': 'Apple Silicon',
    'M2': 'Apple Silicon',
    'M3': 'Apple Silicon',
    'MIPS': 'MIPS',
    'SPARC': 'SPARC',
    '68K': '68K',
}


def find_database() -> Optional[str]:
    """Find the RustChain database file."""
    for path in DEFAULT_DB_PATHS:
        if os.path.exists(path):
            log.info(f"Found database at: {path}")
            return path
    return None


def get_db_connection(db_path: str) -> sqlite3.Connection:
    """Create a database connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_attestation_history(db_path: str, limit: int = 10000) -> List[Dict]:
    """
    Fetch full attestation history from RustChain database.
    
    Queries multiple tables to get comprehensive attestation data:
    - miner_attest_recent: Recent attestations with architecture info
    - miner_fingerprint_history: Historical fingerprint profiles
    - epoch_enroll: Epoch enrollment data
    - balances: RTC balance information
    
    Returns list of attestation records.
    """
    attestations = []
    
    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        
        # Try to query miner_attest_recent table (most common schema)
        try:
            cursor.execute("""
                SELECT 
                    miner,
                    device_arch,
                    device_family,
                    ts_ok as timestamp,
                    fingerprint_passed,
                    entropy_score as fingerprint_quality,
                    warthog_bonus as multiplier
                FROM miner_attest_recent
                WHERE ts_ok IS NOT NULL
                ORDER BY ts_ok DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            log.info(f"Fetched {len(rows)} recent attestations")
            
            for row in rows:
                epoch = calculate_epoch(row['timestamp']) if row['timestamp'] else 0
                attestations.append({
                    'epoch': epoch,
                    'timestamp': row['timestamp'] or 0,
                    'miner_id': row['miner'],
                    'device_arch': normalize_arch(row['device_arch']),
                    'device_family': row['device_family'] or normalize_arch(row['device_arch']),
                    'device_model': 'Unknown',
                    'rtc_earned': 0,  # Would need to calculate from epoch rewards
                    'fingerprint_quality': row['fingerprint_quality'] or 0.5,
                    'multiplier': row['multiplier'] or 1.0,
                    'fingerprint_passed': bool(row['fingerprint_passed'])
                })
                
        except sqlite3.OperationalError as e:
            log.warning(f"miner_attest_recent table not found: {e}")
            
            # Try alternative table names
            try:
                cursor.execute("""
                    SELECT 
                        miner_id,
                        device_arch,
                        device_family,
                        timestamp,
                        fingerprint_quality,
                        multiplier
                    FROM attestations
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
                
                rows = cursor.fetchall()
                log.info(f"Fetched {len(rows)} attestations from alternative table")
                
                for row in rows:
                    attestations.append({
                        'epoch': calculate_epoch(row['timestamp']) if row['timestamp'] else 0,
                        'timestamp': row['timestamp'] or 0,
                        'miner_id': row['miner_id'],
                        'device_arch': normalize_arch(row['device_arch']),
                        'device_family': row['device_family'] or normalize_arch(row['device_arch']),
                        'device_model': 'Unknown',
                        'rtc_earned': 0,
                        'fingerprint_quality': row['fingerprint_quality'] or 0.5,
                        'multiplier': row['multiplier'] or 1.0
                    })
            except sqlite3.OperationalError as e2:
                log.warning(f"Alternative table also not found: {e2}")
        
        conn.close()
        
    except Exception as e:
        log.error(f"Database error: {e}")
    
    return attestations


def calculate_epoch(timestamp: int, genesis_timestamp: int = 1764706927) -> int:
    """
    Calculate epoch number from timestamp.

    RustChain epochs are approximately 24 hours (86400 seconds).
    Genesis timestamp defaults to production chain launch (Dec 2, 2025).
    """
    if not timestamp:
        return 0
    return max(0, (timestamp - genesis_timestamp) // 86400)


def normalize_arch(arch: str) -> str:
    """Normalize architecture name to standard form."""
    if not arch:
        return 'unknown'
    
    arch_upper = arch.upper().strip()
    
    # Check direct mapping
    if arch_upper in ARCH_MAPPING:
        return ARCH_MAPPING[arch_upper]
    
    # Check case-insensitive
    for key, value in ARCH_MAPPING.items():
        if key.upper() == arch_upper:
            return value
    
    # Return as-is if no mapping found
    return arch


def generate_sample_data(num_epochs: int = 150, num_miners: int = 100) -> List[Dict]:
    """
    Generate realistic sample attestation data for demonstration.
    
    Creates a distribution of miners across different architectures
    with realistic attestation patterns over time.
    """
    import random
    
    log.info(f"Generating sample data: {num_epochs} epochs, ~{num_miners} miners")
    
    data = []
    miners = []
    
    # Architecture distribution (mimics real hardware adoption curves)
    arch_profiles = [
        {'arch': 'G4', 'family': 'G4', 'start_epoch': 0, 'count': 15, 'base_rtc': 75, 'multiplier': 2.5},
        {'arch': 'G3', 'family': 'G3', 'start_epoch': 0, 'count': 8, 'base_rtc': 60, 'multiplier': 1.8},
        {'arch': 'G5', 'family': 'G5', 'start_epoch': 10, 'count': 12, 'base_rtc': 80, 'multiplier': 2.0},
        {'arch': 'x86_64', 'family': 'x86_64', 'start_epoch': 0, 'count': 25, 'base_rtc': 50, 'multiplier': 1.0},
        {'arch': 'POWER8', 'family': 'POWER8', 'start_epoch': 20, 'count': 10, 'base_rtc': 70, 'multiplier': 1.5},
        {'arch': 'ppc64le', 'family': 'POWER8', 'start_epoch': 25, 'count': 8, 'base_rtc': 70, 'multiplier': 1.5},
        {'arch': 'ARM', 'family': 'ARM', 'start_epoch': 30, 'count': 12, 'base_rtc': 55, 'multiplier': 1.1},
        {'arch': 'Apple Silicon', 'family': 'Apple Silicon', 'start_epoch': 60, 'count': 10, 'base_rtc': 65, 'multiplier': 1.2},
        {'arch': 'MIPS', 'family': 'MIPS', 'start_epoch': 15, 'count': 5, 'base_rtc': 65, 'multiplier': 1.6},
        {'arch': 'SPARC', 'family': 'SPARC', 'start_epoch': 18, 'count': 4, 'base_rtc': 68, 'multiplier': 1.4},
        {'arch': '68K', 'family': '68K', 'start_epoch': 0, 'count': 3, 'base_rtc': 45, 'multiplier': 3.0},
    ]
    
    # Generate miner profiles
    for profile in arch_profiles:
        for i in range(profile['count']):
            miners.append({
                'id': f"{profile['arch'].lower().replace(' ', '-')}-{i + 1:03d}",
                'arch': profile['arch'],
                'family': profile['family'],
                'model': f"{profile['arch']} Model {i + 1}",
                'start_epoch': profile['start_epoch'] + random.randint(0, 10),
                'base_rtc': profile['base_rtc'] + random.uniform(-10, 20),
                'multiplier': profile['multiplier'],
                'fingerprint_base': 0.65 + random.uniform(0, 0.30)
            })
    
    # Generate attestations across epochs
    genesis_timestamp = 1764706927
    
    for epoch in range(num_epochs + 1):
        epoch_timestamp = genesis_timestamp + (epoch * 86400)
        
        for miner in miners:
            if epoch >= miner['start_epoch']:
                # 85% attestation rate (some missed epochs)
                if random.random() < 0.85:
                    rtc_variance = random.uniform(0.8, 1.2)
                    fp_variance = random.uniform(-0.05, 0.05)
                    
                    data.append({
                        'epoch': epoch,
                        'timestamp': epoch_timestamp,
                        'miner_id': miner['id'],
                        'device_arch': miner['arch'],
                        'device_family': miner['family'],
                        'device_model': miner['model'],
                        'rtc_earned': round(miner['base_rtc'] * rtc_variance, 2),
                        'fingerprint_quality': round(min(1.0, max(0.0, miner['fingerprint_base'] + fp_variance)), 3),
                        'multiplier': miner['multiplier']
                    })
    
    log.info(f"Generated {len(data)} attestation records")
    return data


def export_to_json(data: List[Dict], output_path: str):
    """Export data to JSON file."""
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    log.info(f"Exported {len(data)} records to {output_path}")


def export_to_csv(data: List[Dict], output_path: str):
    """Export data to CSV file."""
    if not data:
        return
    
    headers = list(data[0].keys())
    
    with open(output_path, 'w') as f:
        f.write(','.join(headers) + '\n')
        for row in data:
            values = []
            for h in headers:
                val = row.get(h, '')
                if isinstance(val, str):
                    val = f'"{val}"'
                values.append(str(val))
            f.write(','.join(values) + '\n')
    
    log.info(f"Exported {len(data)} records to CSV: {output_path}")


class FossilRecordHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for the Fossil Record API."""
    
    @lru_cache(maxsize=1)
    def get_cached_data(self):
        """Cache data to avoid repeated DB queries."""
        db_path = find_database()
        if db_path:
            return fetch_attestation_history(db_path)
        else:
            log.warning("No database found, using sample data")
            return generate_sample_data()
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/api/attestations/history':
            self.send_json_response(self.get_cached_data())
        elif self.path == '/api/attestations/sample':
            self.send_json_response(generate_sample_data())
        elif self.path == '/':
            self.path = '/fossils/index.html'
            return SimpleHTTPRequestHandler.do_GET(self)
        else:
            return SimpleHTTPRequestHandler.do_GET(self)
    
    def send_json_response(self, data):
        """Send JSON response."""
        response = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response))
        self.send_header('Access-Control-Allow-Origin', 'https://rustchain.io')
        self.end_headers()
        self.wfile.write(response)


def serve(port: int = 8080):
    """Start HTTP server for the visualizer."""
    server = HTTPServer(('0.0.0.0', port), FossilRecordHandler)
    log.info(f"Starting Fossil Record server at http://localhost:{port}")
    log.info("Serving visualizer at: http://localhost:{port}/fossils/index.html")
    log.info("API endpoints:")
    log.info("  GET /api/attestations/history - Full attestation history")
    log.info("  GET /api/attestations/sample  - Sample data for testing")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Server stopped")
        server.shutdown()


def main():
    parser = argparse.ArgumentParser(
        description='The Fossil Record — Attestation Archaeology Data Export',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --export history.json          # Export from database
  %(prog)s --sample --output sample.json  # Generate sample data
  %(prog)s --serve                        # Start HTTP server
  %(prog)s --db /path/to/db.sqlite3 --export data.json
        """
    )
    
    parser.add_argument('--db', help='Path to RustChain database')
    parser.add_argument('--export', metavar='FILE', help='Export attestations to JSON file')
    parser.add_argument('--csv', metavar='FILE', help='Export attestations to CSV file')
    parser.add_argument('--sample', action='store_true', help='Generate sample data')
    parser.add_argument('--output', '-o', help='Output file for sample data')
    parser.add_argument('--epochs', type=int, default=150, help='Number of epochs for sample data')
    parser.add_argument('--miners', type=int, default=100, help='Number of miners for sample data')
    parser.add_argument('--serve', action='store_true', help='Start HTTP server')
    parser.add_argument('--port', type=int, default=8080, help='HTTP server port')
    parser.add_argument('--limit', type=int, default=10000, help='Max records to export')
    
    args = parser.parse_args()
    
    if args.serve:
        serve(args.port)
        return
    
    if args.sample:
        data = generate_sample_data(args.epochs, args.miners)
        output = args.output or 'sample_data.json'
        export_to_json(data, output)
        log.info(f"Sample data saved to: {output}")
        
        if args.csv:
            export_to_csv(data, args.csv)
        return
    
    if args.export:
        db_path = args.db or find_database()
        if not db_path:
            log.error("No database found. Use --db to specify path, or --sample to generate demo data")
            sys.exit(1)
        
        data = fetch_attestation_history(db_path, args.limit)
        export_to_json(data, args.export)
        
        if args.csv:
            export_to_csv(data, args.csv)
        return
    
    # Default: show help
    parser.print_help()


if __name__ == '__main__':
    main()
