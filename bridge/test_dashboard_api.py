"""
Tests for wRTC Solana Bridge Dashboard API

Run with:
    python3 -m pytest bridge/test_dashboard_api.py -v

Coverage:
- Dashboard metrics endpoint
- Health check endpoint
- Transactions endpoint
- Price endpoint
- Chart endpoint
"""

import pytest
import json
import time
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from bridge.bridge_api import register_bridge_routes, init_bridge_db, get_db, _amount_to_base, STATE_COMPLETE
from bridge.dashboard_api import build_live_bridge_health, register_dashboard_routes


@pytest.fixture
def app():
    """Create test Flask application."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['BRIDGE_DB_PATH'] = ':memory:'
    
    # Initialize database
    init_bridge_db()
    
    # Register blueprints
    register_bridge_routes(app)
    register_dashboard_routes(app)
    
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def sample_lock_data():
    """Sample lock data for testing."""
    return {
        'lock_id': 'lock_test123',
        'sender_wallet': 'test-wallet',
        'amount_rtc': 100.0,
        'target_chain': 'solana',
        'target_wallet': '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU',
        'tx_hash': 'test-tx-hash-123',
        'state': STATE_COMPLETE,
    }


def insert_sample_lock(db_path, lock_data):
    """Insert sample lock into database with unique tx_hash."""
    import uuid
    with get_db() as conn:
        now = int(time.time())
        tx_hash = lock_data.get('tx_hash', f'test-tx-{uuid.uuid4().hex[:8]}')
        conn.execute(
            """
            INSERT INTO bridge_locks
            (lock_id, sender_wallet, amount_rtc, target_chain, target_wallet,
             state, tx_hash, created_at, updated_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lock_data['lock_id'],
                lock_data['sender_wallet'],
                _amount_to_base(lock_data['amount_rtc']),
                lock_data['target_chain'],
                lock_data['target_wallet'],
                lock_data['state'],
                tx_hash,
                now,
                now,
                now + 86400,
            )
        )
        conn.commit()


class TestDashboardMetrics:
    """Test /bridge/dashboard/metrics endpoint."""

    def test_metrics_endpoint_exists(self, client):
        """Test metrics endpoint returns data."""
        response = client.get('/bridge/dashboard/metrics')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'total_locked_rtc' in data
        assert 'wrtc_circulating' in data
        assert 'fee_revenue' in data

    def test_metrics_with_data(self, app, client):
        """Test metrics with sample data."""
        import uuid
        
        # Get baseline metrics
        baseline_resp = client.get('/bridge/dashboard/metrics')
        baseline = json.loads(baseline_resp.data)
        baseline_total = baseline['total_locked_rtc']
        
        # Insert sample lock
        insert_sample_lock(app.config['BRIDGE_DB_PATH'], {
            'lock_id': f'lock_test_{uuid.uuid4().hex[:8]}',
            'sender_wallet': 'wallet1',
            'amount_rtc': 500.0,
            'target_chain': 'solana',
            'target_wallet': '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU',
            'tx_hash': f'tx1-{uuid.uuid4().hex[:8]}',
            'state': STATE_COMPLETE,
        })
        
        response = client.get('/bridge/dashboard/metrics')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Check that total increased by at least 500
        assert data['total_locked_rtc'] >= baseline_total + 500.0
        assert data['wrtc_circulating'] >= 500.0
        assert data['fee_revenue'] > 0  # Should have some fees
        assert data['total_transactions'] >= 1

    def test_metrics_format(self, client):
        """Test metrics response format."""
        response = client.get('/bridge/dashboard/metrics')
        data = json.loads(response.data)
        
        assert isinstance(data['total_locked_rtc'], (int, float))
        assert isinstance(data['wrtc_circulating'], (int, float))
        assert isinstance(data['fee_revenue'], (int, float))
        assert isinstance(data['locked_change_24h'], (int, float))
        assert isinstance(data['circulating_change_24h'], (int, float))
        assert isinstance(data['total_transactions'], int)
        assert isinstance(data['last_updated'], int)


class TestBridgeHealth:
    """Test /bridge/dashboard/health endpoint."""

    def test_health_endpoint_exists(self, client):
        """Test health endpoint returns data."""
        response = client.get('/bridge/dashboard/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'overall' in data
        assert 'components' in data
        assert 'last_checked' in data

    def test_health_components(self, client):
        """Test health check includes all components."""
        response = client.get('/bridge/dashboard/health')
        data = json.loads(response.data)
        
        components = data['components']
        assert 'rustchain' in components
        assert 'solana_rpc' in components
        assert 'bridge_api' in components
        assert 'wrtc_mint' in components

    def test_health_overall_status(self, client):
        """Test overall health status is valid."""
        response = client.get('/bridge/dashboard/health')
        data = json.loads(response.data)
        
        assert data['overall'] in ['healthy', 'degraded', 'offline']

    def test_health_timestamp(self, client):
        """Test health check includes recent timestamp."""
        response = client.get('/bridge/dashboard/health')
        data = json.loads(response.data)
        
        now = int(time.time())
        assert abs(data['last_checked'] - now) < 5  # Within 5 seconds


class TestLiveBridgeHealth:
    """Test bridge health JSONL aggregation for real-time dashboard data."""

    def test_live_bridge_health_missing_log_is_offline(self, tmp_path):
        result = build_live_bridge_health(str(tmp_path / "missing.jsonl"), now=1000)

        assert result["bridge_status"] == "OFFLINE"
        assert result["alerts"][0]["type"] == "no_health_events"
        assert result["sample_count"] == 0

    def test_live_bridge_health_aggregates_status_alerts_and_analytics(self, tmp_path):
        health_log = tmp_path / "bridge_health.jsonl"
        events = [
            {"ts": 1000, "bridge_status": "ACTIVE", "pending_txs": 10, "solana_slot_diff": 100, "settlement_time_s": 20},
            {"ts": 1300, "bridge_status": "ACTIVE", "pending_txs": 55, "solana_slot_diff": 120, "settlement_time_s": 40},
            {"ts": 1700, "bridge_status": "DEGRADED", "pending_txs": 60, "solana_slot_diff": 1200, "failed_reason": "solana_timeout"},
        ]
        health_log.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")

        result = build_live_bridge_health(str(health_log), now=1800)

        assert result["bridge_status"] == "DEGRADED"
        assert result["pending_txs"] == 60
        assert result["solana_slot_diff"] == 1200
        assert {alert["type"] for alert in result["alerts"]} == {"pending_txs_high", "solana_slot_lag"}
        assert result["analytics"]["uptime_24h_pct"] == 66.67
        assert result["analytics"]["avg_settlement_time_s"] == 30.0
        assert result["analytics"]["failed_tx_breakdown"] == {"solana_timeout": 1}

    def test_live_bridge_health_stale_active_sample_is_offline(self, tmp_path):
        health_log = tmp_path / "bridge_health.jsonl"
        health_log.write_text(
            json.dumps({
                "ts": 1000,
                "bridge_status": "ACTIVE",
                "pending_txs": 0,
                "solana_slot_diff": 0,
            }) + "\n",
            encoding="utf-8",
        )

        result = build_live_bridge_health(str(health_log), now=1400)

        assert result["bridge_status"] == "OFFLINE"
        assert result["last_event_ts"] == 1000

    def test_live_bridge_endpoint_rejects_bad_limit(self, client):
        response = client.get('/bridge/dashboard/live?limit=abc')

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] == "limit must be an integer"


class TestDashboardTransactions:
    """Test /bridge/dashboard/transactions endpoint."""

    def test_transactions_endpoint_exists(self, client):
        """Test transactions endpoint returns data."""
        response = client.get('/bridge/dashboard/transactions')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'transactions' in data
        assert 'wrap_count' in data
        assert 'unwrap_count' in data

    def test_transactions_with_data(self, app, client):
        """Test transactions with sample data."""
        import uuid
        insert_sample_lock(app.config['BRIDGE_DB_PATH'], {
            'lock_id': f'lock_tx_{uuid.uuid4().hex[:8]}',
            'sender_wallet': 'wallet1',
            'amount_rtc': 100.0,
            'target_chain': 'solana',
            'target_wallet': '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU',
            'tx_hash': f'tx-tx-{uuid.uuid4().hex[:8]}',
            'state': STATE_COMPLETE,
        })
        
        response = client.get('/bridge/dashboard/transactions')
        data = json.loads(response.data)
        
        assert len(data['transactions']) >= 1
        assert data['wrap_count'] >= 1

    def test_transactions_limit(self, client):
        """Test transactions limit parameter."""
        response = client.get('/bridge/dashboard/transactions?limit=10')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should respect limit
        assert len(data['transactions']) <= 10

    def test_transactions_max_limit(self, client):
        """Test transactions max limit enforcement."""
        response = client.get('/bridge/dashboard/transactions?limit=500')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should cap at 200
        assert len(data['transactions']) <= 200

    def test_transactions_rejects_non_integer_limit(self, client):
        """Test transactions limit rejects malformed values."""
        response = client.get('/bridge/dashboard/transactions?limit=abc')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error'] == 'limit must be an integer'

    def test_transactions_clamps_negative_limit(self, app, client):
        """Test transactions limit clamps negative values to one row."""
        import uuid

        for idx in range(2):
            insert_sample_lock(app.config['BRIDGE_DB_PATH'], {
                'lock_id': f'lock_neg_{idx}_{uuid.uuid4().hex[:8]}',
                'sender_wallet': f'wallet-neg-{idx}',
                'amount_rtc': 100.0 + idx,
                'target_chain': 'solana',
                'target_wallet': '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU',
                'tx_hash': f'tx-neg-{uuid.uuid4().hex[:8]}',
                'state': STATE_COMPLETE,
            })

        response = client.get('/bridge/dashboard/transactions?limit=-1')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['transactions']) == 1

    def test_transactions_type_filter_wrap_and_unwrap(self, app, client):
        """Test transactions type filter applies wrap/unwrap query parameter."""
        import uuid

        insert_sample_lock(app.config['BRIDGE_DB_PATH'], {
            'lock_id': f'lock_wrap_{uuid.uuid4().hex[:8]}',
            'sender_wallet': 'wallet-wrap',
            'amount_rtc': 100.0,
            'target_chain': 'solana',
            'target_wallet': '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU',
            'tx_hash': f'tx-wrap-{uuid.uuid4().hex[:8]}',
            'state': STATE_COMPLETE,
        })
        insert_sample_lock(app.config['BRIDGE_DB_PATH'], {
            'lock_id': f'lock_unwrap_{uuid.uuid4().hex[:8]}',
            'sender_wallet': 'wallet-unwrap',
            'amount_rtc': 75.0,
            'target_chain': 'base',
            'target_wallet': '0x1111111111111111111111111111111111111111',
            'tx_hash': f'tx-unwrap-{uuid.uuid4().hex[:8]}',
            'state': STATE_COMPLETE,
        })

        wrap_response = client.get('/bridge/dashboard/transactions?type=wrap')
        unwrap_response = client.get('/bridge/dashboard/transactions?type=unwrap')

        assert wrap_response.status_code == 200
        assert unwrap_response.status_code == 200
        wrap_data = json.loads(wrap_response.data)
        unwrap_data = json.loads(unwrap_response.data)
        assert wrap_data['transactions']
        assert unwrap_data['transactions']
        assert {tx['type'] for tx in wrap_data['transactions']} == {'wrap'}
        assert {tx['type'] for tx in unwrap_data['transactions']} == {'unwrap'}

    def test_transactions_rejects_unknown_type(self, client):
        """Test transactions type filter rejects unsupported values."""
        response = client.get('/bridge/dashboard/transactions?type=sideways')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error'] == 'type must be one of: all, wrap, unwrap'

    def test_transactions_format(self, client):
        """Test transaction format."""
        response = client.get('/bridge/dashboard/transactions')
        data = json.loads(response.data)
        
        assert isinstance(data['transactions'], list)
        assert isinstance(data['wrap_count'], int)
        assert isinstance(data['unwrap_count'], int)
        assert isinstance(data['total_volume_24h'], (int, float))


class TestWrtcPrice:
    """Test /bridge/dashboard/price endpoint."""

    def test_price_endpoint_exists(self, client):
        """Test price endpoint exists."""
        response = client.get('/bridge/dashboard/price')
        # May return 404 if WRTC_MINT_ADDRESS not configured
        assert response.status_code in [200, 404, 503]

    def test_price_format(self, client):
        """Test price response format."""
        response = client.get('/bridge/dashboard/price')
        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'price_usd' in data
            assert 'change_24h' in data
            assert 'source' in data


class TestPriceChart:
    """Test /bridge/dashboard/chart endpoint."""

    def test_chart_endpoint_exists(self, client):
        """Test chart endpoint returns data."""
        response = client.get('/bridge/dashboard/chart')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_chart_periods(self, client):
        """Test different chart periods."""
        for period in ['1h', '24h', '7d', '30d']:
            response = client.get(f'/bridge/dashboard/chart?period={period}')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert isinstance(data, list)
            assert len(data) > 0

    def test_chart_data_format(self, client):
        """Test chart data point format."""
        response = client.get('/bridge/dashboard/chart?period=24h')
        data = json.loads(response.data)
        
        assert len(data) > 0
        point = data[0]
        assert 'timestamp' in point
        assert 'price' in point
        assert 'volume' in point


class TestIntegration:
    """Integration tests for dashboard."""

    def test_full_dashboard_flow(self, app, client):
        """Test complete dashboard data flow."""
        import uuid
        
        # Insert test data with unique tx_hash
        lock_id = f'lock_int_{uuid.uuid4().hex[:8]}'
        insert_sample_lock(app.config['BRIDGE_DB_PATH'], {
            'lock_id': lock_id,
            'sender_wallet': 'wallet-int',
            'amount_rtc': 1000.0,
            'target_chain': 'solana',
            'target_wallet': '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU',
            'tx_hash': f'tx-int-{uuid.uuid4().hex[:8]}',
            'state': STATE_COMPLETE,
        })
        
        # Get metrics
        metrics_resp = client.get('/bridge/dashboard/metrics')
        metrics = json.loads(metrics_resp.data)
        # Check that locked is at least 1000 (may have other test data)
        assert metrics['total_locked_rtc'] >= 1000.0
        
        # Get health
        health_resp = client.get('/bridge/dashboard/health')
        health = json.loads(health_resp.data)
        assert health['overall'] in ['healthy', 'degraded', 'offline']
        
        # Get transactions
        tx_resp = client.get('/bridge/dashboard/transactions')
        tx = json.loads(tx_resp.data)
        assert tx['wrap_count'] >= 1
        
        # Get chart
        chart_resp = client.get('/bridge/dashboard/chart')
        chart = json.loads(chart_resp.data)
        assert len(chart) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
