def test_wallet_history_basic(client):
    """Test the wallet history endpoint returns expected structure."""
    response = client.get('/wallet/history?wallet=test123')
    assert response.status_code == 200
    data = response.json()
    assert 'ok' in data
    assert 'miner_id' in data
    assert 'transactions' in data
    assert 'total' in data
    assert isinstance(data['transactions'], list)
    if len(data['transactions']) > 0:
        tx = data['transactions'][0]
        assert 'tx_id' in tx
        assert 'amount' in tx
        assert 'timestamp' in tx
        assert 'direction' in tx