from flask import Flask, render_template, jsonify
import os
import requests
import json
from datetime import datetime

app = Flask(__name__)

# Configuration
API_BASE_URL = "http://localhost:8000"
MINERS_ENDPOINT = f"{API_BASE_URL}/api/miners"
FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/miners')
def get_miners():
    try:
        response = requests.get(MINERS_ENDPOINT, timeout=5)
        if response.status_code == 200:
            miners_data = response.json()
            
            # Enhance miner data with additional calculated fields
            for miner in miners_data.get('miners', []):
                # Calculate uptime percentage
                if 'uptime' in miner:
                    miner['uptime_percentage'] = min(100, (miner['uptime'] / 86400) * 100)
                
                # Format last seen timestamp
                if 'last_seen' in miner:
                    try:
                        timestamp = datetime.fromtimestamp(miner['last_seen'])
                        miner['last_seen_formatted'] = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        miner['last_seen_formatted'] = 'Unknown'
                
                # Set status based on last seen
                if 'last_seen' in miner:
                    time_diff = datetime.now().timestamp() - miner['last_seen']
                    if time_diff < 300:  # 5 minutes
                        miner['status'] = 'online'
                    elif time_diff < 3600:  # 1 hour
                        miner['status'] = 'idle'
                    else:
                        miner['status'] = 'offline'
                else:
                    miner['status'] = 'unknown'
            
            return jsonify(miners_data)
        else:
            return jsonify({'error': 'Failed to fetch miners data', 'miners': []}), 500
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Connection error: {str(e)}', 'miners': []}), 500

@app.route('/api/network/stats')
def get_network_stats():
    try:
        miners_response = requests.get(MINERS_ENDPOINT, timeout=5)
        if miners_response.status_code == 200:
            miners_data = miners_response.json()
            miners = miners_data.get('miners', [])
            
            # Calculate network statistics
            total_miners = len(miners)
            active_miners = len([m for m in miners if m.get('status') == 'online'])
            total_hashrate = sum([m.get('hashrate', 0) for m in miners])
            
            # Calculate average block time (mock data for now)
            avg_block_time = 60  # seconds
            
            stats = {
                'total_miners': total_miners,
                'active_miners': active_miners,
                'total_hashrate': total_hashrate,
                'network_difficulty': 1000000,  # Mock data
                'avg_block_time': avg_block_time,
                'last_updated': datetime.now().isoformat()
            }
            
            return jsonify(stats)
        else:
            return jsonify({'error': 'Failed to fetch network stats'}), 500
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Connection error: {str(e)}'}), 500

@app.route('/miner/<miner_id>')
def miner_detail(miner_id):
    return render_template('miner_detail.html', miner_id=miner_id)

@app.route('/api/miner/<miner_id>')
def get_miner_detail(miner_id):
    try:
        response = requests.get(MINERS_ENDPOINT, timeout=5)
        if response.status_code == 200:
            miners_data = response.json()
            miners = miners_data.get('miners', [])
            
            # Find specific miner
            miner = next((m for m in miners if m.get('id') == miner_id), None)
            
            if miner:
                # Enhance miner data
                if 'last_seen' in miner:
                    try:
                        timestamp = datetime.fromtimestamp(miner['last_seen'])
                        miner['last_seen_formatted'] = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        miner['last_seen_formatted'] = 'Unknown'
                
                # Calculate status
                if 'last_seen' in miner:
                    time_diff = datetime.now().timestamp() - miner['last_seen']
                    if time_diff < 300:
                        miner['status'] = 'online'
                    elif time_diff < 3600:
                        miner['status'] = 'idle'
                    else:
                        miner['status'] = 'offline'
                
                return jsonify(miner)
            else:
                return jsonify({'error': 'Miner not found'}), 404
        else:
            return jsonify({'error': 'Failed to fetch miner data'}), 500
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Connection error: {str(e)}'}), 500

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=FLASK_DEBUG)
