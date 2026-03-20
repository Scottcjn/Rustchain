// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, jsonify
import sqlite3
import requests
import json
from datetime import datetime
import os

app = Flask(__name__)
DB_PATH = 'rustchain.db'

# Known node endpoints
NODES = [
    'https://50.28.86.131',
    # Add more nodes as they come online
]

def fetch_node_data(node_url, endpoint, timeout=10):
    """Fetch data from a specific node endpoint with error handling."""
    try:
        url = f"{node_url}{endpoint}"
        response = requests.get(url, timeout=timeout, verify=False)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {'error': str(e)}
    except json.JSONDecodeError:
        return {'error': 'Invalid JSON response'}

def get_network_miners():
    """Aggregate miner data from all available nodes."""
    all_miners = {}
    active_nodes = 0

    for node in NODES:
        miners_data = fetch_node_data(node, '/api/miners')
        if 'error' not in miners_data:
            active_nodes += 1
            if isinstance(miners_data, dict) and 'miners' in miners_data:
                for miner_id, miner_info in miners_data['miners'].items():
                    if miner_id not in all_miners:
                        all_miners[miner_id] = miner_info
                        all_miners[miner_id]['seen_on_nodes'] = 1
                    else:
                        all_miners[miner_id]['seen_on_nodes'] += 1

    return all_miners, active_nodes

def get_network_health():
    """Check health status across all nodes."""
    health_status = {}

    for node in NODES:
        node_health = fetch_node_data(node, '/health')
        health_status[node] = node_health

    return health_status

def get_epoch_info():
    """Get current epoch information from primary node."""
    epoch_data = fetch_node_data(NODES[0], '/epoch') if NODES else {}
    return epoch_data

def get_db_stats():
    """Get basic blockchain statistics from local database."""
    stats = {
        'total_blocks': 0,
        'total_transactions': 0,
        'last_block_time': None
    }

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get block count
            cursor.execute("SELECT COUNT(*) FROM blocks")
            stats['total_blocks'] = cursor.fetchone()[0]

            # Get transaction count
            cursor.execute("SELECT COUNT(*) FROM transactions")
            stats['total_transactions'] = cursor.fetchone()[0]

            # Get latest block timestamp
            cursor.execute("SELECT timestamp FROM blocks ORDER BY height DESC LIMIT 1")
            result = cursor.fetchone()
            if result:
                stats['last_block_time'] = result[0]

    except sqlite3.Error as e:
        stats['db_error'] = str(e)

    return stats

@app.route('/api/status')
def network_status():
    """Main status endpoint that aggregates all network data."""

    # Collect data from various sources
    miners_data, active_nodes = get_network_miners()
    health_data = get_network_health()
    epoch_info = get_epoch_info()
    db_stats = get_db_stats()

    # Calculate network statistics
    total_miners = len(miners_data)
    active_miners = sum(1 for m in miners_data.values() if m.get('status') == 'active')

    # Hardware distribution
    hardware_types = {}
    for miner in miners_data.values():
        hw_type = miner.get('hardware_type', 'unknown')
        hardware_types[hw_type] = hardware_types.get(hw_type, 0) + 1

    # Node status summary
    healthy_nodes = sum(1 for status in health_data.values()
                       if isinstance(status, dict) and status.get('status') == 'healthy')

    response = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'network': {
            'name': 'RustChain',
            'type': 'Proof-of-Antiquity',
            'token': 'RTC',
            'nodes': {
                'total': len(NODES),
                'healthy': healthy_nodes,
                'responding': active_nodes
            }
        },
        'miners': {
            'total': total_miners,
            'active': active_miners,
            'hardware_distribution': hardware_types,
            'details': miners_data
        },
        'blockchain': {
            'total_blocks': db_stats.get('total_blocks', 0),
            'total_transactions': db_stats.get('total_transactions', 0),
            'last_block_time': db_stats.get('last_block_time'),
            'current_epoch': epoch_info.get('current_epoch'),
            'epoch_progress': epoch_info.get('progress')
        },
        'nodes_health': health_data
    }

    # Add any database errors to the response
    if 'db_error' in db_stats:
        response['errors'] = response.get('errors', [])
        response['errors'].append(f"Database error: {db_stats['db_error']}")

    return jsonify(response)

@app.route('/api/miners')
def miners_endpoint():
    """Dedicated miners endpoint for backward compatibility."""
    miners_data, _ = get_network_miners()
    return jsonify({'miners': miners_data, 'count': len(miners_data)})

@app.route('/api/health')
def health_check():
    """Simple health check for the status API itself."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'service': 'rustchain-status-api'
    })

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)
