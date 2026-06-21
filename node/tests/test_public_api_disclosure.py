def test_wallet_history_disclosure(client):
    """Test wallet history endpoint follows public API contract."""
    response = client.get('/wallet/history?wallet=test123')
    assert response.status_code == 200
    data = response.json()
    
    # Check envelope structure
    assert set(data.keys()) == {'ok', 'miner_id', 'transactions', 'total'}
    assert isinstance(data['transactions'], list)
    
    # Check transaction structure
    if data['transactions']:
        tx = data['transactions'][0]
        assert set(tx.keys()).issuperset({'tx_id', 'amount', 'timestamp', 'direction'})