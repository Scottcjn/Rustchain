import pytest
import sqlite3
import tempfile
import os
import json
from flask import Flask
from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant
from node.rustchain_block_producer import BlockProducer, BlockValidator, create_block_api_routes

class MockTxPool:
    def __init__(self, db_path):
        self.db_path = db_path

@pytest.fixture
def test_app():
    """Setup a test Flask app with the explorer endpoints"""
    fd, db_path = tempfile.mkstemp()
    os.close(fd)
    
    # Initialize DB schema
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS blocks (
                height INTEGER PRIMARY KEY,
                block_hash TEXT UNIQUE NOT NULL,
                timestamp INTEGER NOT NULL,
                prev_hash TEXT, merkle_root TEXT, state_root TEXT,
                attestations_hash TEXT, producer TEXT, producer_sig TEXT,
                tx_count INTEGER, attestation_count INTEGER, body_json TEXT, created_at INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                tx_hash TEXT PRIMARY KEY,
                timestamp INTEGER NOT NULL,
                from_addr TEXT, to_addr TEXT, amount_urtc INTEGER,
                nonce INTEGER, block_height INTEGER
            )
        """)
        
        # Insert 50 dummy blocks
        for i in range(50):
            conn.execute(
                "INSERT INTO blocks (height, block_hash, timestamp) VALUES (?, ?, ?)",
                (i, f"hash_{i}", 1000 + i)
            )
        
        # Insert 50 dummy transactions
        for i in range(50):
            conn.execute(
                "INSERT INTO transactions (tx_hash, timestamp) VALUES (?, ?)",
                (f"tx_{i}", 2000 + i)
            )
            
    app = Flask(__name__)
    producer = BlockProducer(db_path, MockTxPool(db_path))
    validator = BlockValidator(db_path)
    create_block_api_routes(app, producer, validator)
    
    client = app.test_client()
    yield client
    
    if os.path.exists(db_path):
        os.unlink(db_path)

def test_api_blocks_default(test_app):
    """Test /api/blocks with default parameters"""
    response = test_app.get('/api/blocks')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 10  # Default limit
    assert data[0]['height'] == 49  # Ordered by height DESC

def test_api_blocks_valid_limit(test_app):
    """Test /api/blocks with valid limit"""
    response = test_app.get('/api/blocks?limit=5')
    assert response.status_code == 200
    assert len(json.loads(response.data)) == 5

def test_api_blocks_limit_cap(test_app):
    """Test /api/blocks with limit at cap (1000)"""
    response = test_app.get('/api/blocks?limit=1000')
    assert response.status_code == 200
    # Only 50 in DB, so should return 50
    assert len(json.loads(response.data)) == 50

def test_api_blocks_limit_exceeding_cap(test_app):
    """Test /api/blocks with limit exceeding cap (1001)"""
    # Should be capped at 1000, not rejected
    response = test_app.get('/api/blocks?limit=1001')
    assert response.status_code == 200

def test_api_blocks_limit_zero(test_app):
    """Test /api/blocks with limit zero"""
    response = test_app.get('/api/blocks?limit=0')
    assert response.status_code == 200
    assert len(json.loads(response.data)) == 0

def test_api_blocks_negative_limit(test_app):
    """Test /api/blocks with negative limit (expect 400)"""
    response = test_app.get('/api/blocks?limit=-1')
    assert response.status_code == 400

def test_api_blocks_offset(test_app):
    """Test /api/blocks with valid offset"""
    response = test_app.get('/api/blocks?limit=5&offset=10')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 5
    assert data[0]['height'] == 39  # 49 - 10

def test_api_blocks_negative_offset(test_app):
    """Test /api/blocks with negative offset (verify capped to 0)"""
    response = test_app.get('/api/blocks?offset=-10')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data[0]['height'] == 49

def test_api_blocks_offset_exceeding_total(test_app):
    """Test /api/blocks with offset exceeding total records"""
    response = test_app.get('/api/blocks?offset=100')
    assert response.status_code == 200
    assert len(json.loads(response.data)) == 0

def test_api_blocks_non_integer_limit(test_app):
    """Test /api/blocks with non-integer limit"""
    response = test_app.get('/api/blocks?limit=abc')
    assert response.status_code == 400

def test_api_blocks_non_integer_offset(test_app):
    """Test /api/blocks with non-integer offset"""
    response = test_app.get('/api/blocks?offset=xyz')
    assert response.status_code == 400

def test_api_transactions_default(test_app):
    """Test /api/transactions with default parameters"""
    response = test_app.get('/api/transactions')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 10
    assert data[0]['tx_hash'] == 'tx_49'

def test_api_no_matching_records(test_app):
    """Test API with no matching records"""
    # Create a fresh empty DB
    fd, db_path = tempfile.mkstemp()
    os.close(fd)
    app = Flask(__name__)
    producer = BlockProducer(db_path, MockTxPool(db_path))
    create_block_api_routes(app, producer, BlockValidator(db_path))
    client = app.test_client()
    
    response = client.get('/api/blocks')
    assert response.status_code == 200
    assert json.loads(response.data) == []
    os.unlink(db_path)

@settings(max_examples=10000, stateful_step_count=50)
class ExplorerAPIStateMachine(RuleBasedStateMachine):
    """Stateful property-based tests for Explorer API"""
    def __init__(self):
        super().__init__()
        fd, self.db_path = tempfile.mkstemp()
        os.close(fd)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE blocks (height INTEGER PRIMARY KEY)")
            for i in range(100):
                conn.execute("INSERT INTO blocks (height) VALUES (?)", (i,))
        
        self.app = Flask(__name__)
        producer = BlockProducer(self.db_path, MockTxPool(self.db_path))
        create_block_api_routes(self.app, producer, BlockValidator(self.db_path))
        self.client = self.app.test_client()

    @rule(limit=st.integers(min_value=-10, max_value=2000), 
          offset=st.integers(min_value=-10, max_value=200))
    def check_blocks_endpoint(self, limit, offset):
        response = self.client.get(f'/api/blocks?limit={limit}&offset={offset}')
        
        if limit < 0:
            assert response.status_code == 400
        else:
            assert response.status_code == 200
            data = json.loads(response.data)
            # Invariant: Never return more than the cap
            assert len(data) <= 1000
            # Invariant: Never return more than requested (capped at 1000)
            assert len(data) <= min(limit, 1000)

    @invariant()
    def teardown(self):
        if hasattr(self, 'db_path') and os.path.exists(self.db_path):
            try:
                os.unlink(self.db_path)
            except:
                pass

def test_explorer_api_stateful():
    """Run Hypothesis stateful tests"""
    ExplorerAPIStateMachine.run()
