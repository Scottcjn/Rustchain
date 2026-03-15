# RustChain CI Test Suite

Pytest-based test suite for the RustChain node API, wallet operations, and epoch handling.

## Structure

| File | Coverage |
|------|----------|
| `conftest.py` | Shared fixtures, module loading, mock crypto setup |
| `test_api_endpoints.py` | All HTTP API endpoints: health, epoch, mining, stats, attestation, governance, beacon, withdrawals, admin |
| `test_wallet_operations.py` | Wallet balance, history, admin transfers (2-phase commit), signed transfers, ledger, resolve |
| `test_epoch_handling.py` | Slot/epoch math, enrollment lifecycle, reward settlement, VRF selection, epoch boundaries, chain config |
| `pytest.ini` | Test runner configuration and markers |

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run by marker
pytest tests/ -m wallet
pytest tests/ -m epoch
pytest tests/ -m admin

# Run a single file
pytest tests/test_api_endpoints.py -v
```

## Requirements

- Python 3.9+
- Flask (test client)
- pytest

All tests use the Flask test client and mock the SQLite database, so no running node is required.

## Markers

- `slow` -- long-running tests (deselect with `-m "not slow"`)
- `admin` -- tests that exercise admin-authenticated endpoints
- `wallet` -- wallet operation tests
- `epoch` -- epoch transition tests
