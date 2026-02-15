# GitHub Actions CI Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a complete CI/CD pipeline with 10+ unit tests covering hardware fingerprinting, blockchain logic, ledger operations, and API responses.

**Architecture:** A modular pytest-based test suite in the `tests/` directory, using `conftest.py` for shared fixtures (mock database, hardware data). The CI pipeline is managed by GitHub Actions, running linting, type checking, security scanning, and tests on every PR.

**Tech Stack:** Python 3.11, pytest, ruff, mypy, bandit, GitHub Actions.

---

### Task 1: Initialize Test Infrastructure

**Files:**
- Create: `pyproject.toml`
- Create: `tests/conftest.py`
- Modify: `README.md`

**Step 1: Write initial pyproject.toml with ruff and pytest config**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["node"]

[tool.ruff]
line-length = 100
select = ["E", "F", "W", "B", "I"]
ignore = []

[tool.ruff.per-file-ignores]
"node/*.py" = ["E501"] # Ignore long lines in legacy code
```

**Step 2: Create tests directory and basic conftest.py with DB fixture**
```python
import pytest
import sqlite3
import os

@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    # Initialize schema here if possible, or mock the manager
    yield conn
    conn.close()
```

**Step 3: Add CI badge to README.md**
```markdown
[![CI](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml/badge.svg)](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml)
```

**Step 4: Commit**
```bash
git add pyproject.toml tests/conftest.py README.md
git commit -m "chore: initialize CI infrastructure and add badge"
```

---

### Task 2: Hardware Fingerprint Tests

**Files:**
- Create: `tests/test_fingerprint.py`

**Step 1: Write tests for _compute_hardware_id**
- Verify unique hashes for different IPs/MACs.
- Verify consistency for same inputs.

**Step 2: Write tests for validate_fingerprint_data**
- Mock architecture and check drift thresholds.
- Test VM detection logic (simulated failure).

**Step 3: Run tests**
`pytest tests/test_fingerprint.py -v`

**Step 4: Commit**
```bash
git add tests/test_fingerprint.py
git commit -m "test: add hardware fingerprinting unit tests"
```

---

### Task 3: Blockchain Logic Tests

**Files:**
- Create: `tests/test_blockchain.py`

**Step 1: Write tests for current_slot**
- Mock time and genesis timestamp.
- Verify correct slot calculation.

**Step 2: Write tests for multiplier lookups**
- Test `get_time_aged_multiplier` for G4, G5, and Modern x86.
- Verify decay logic.

**Step 3: Run tests**
`pytest tests/test_blockchain.py -v`

**Step 4: Commit**
```bash
git add tests/test_blockchain.py
git commit -m "test: add slot calculation and multiplier tests"
```

---

### Task 4: Ledger and Address Validation Tests

**Files:**
- Create: `tests/test_ledger.py`

**Step 1: Write tests for balance operations**
- Test credit, debit, and transfer.
- Mock the SQLite DB manager.

**Step 2: Write tests for address validation**
- Test RTC address format and public key derivation.

**Step 3: Write tests for nonce replay protection**
- Verify duplicate transaction detection.

**Step 4: Run tests**
`pytest tests/test_ledger.py -v`

**Step 5: Commit**
```bash
git add tests/test_ledger.py
git commit -m "test: add ledger, address, and nonce protection tests"
```

---

### Task 5: API and Final CI Workflow

**Files:**
- Create: `tests/test_api.py`
- Create: `.github/workflows/ci.yml`

**Step 1: Write tests for API responses**
- Mock health, epoch, and miners endpoints.

**Step 2: Implement full GitHub Actions workflow**
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - name: Install dependencies
        run: |
          pip install ruff mypy pytest pytest-mock bandit
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
      - name: Lint
        run: ruff check .
      - name: Type check
        run: mypy . --ignore-missing-imports || true
      - name: Security scan
        run: bandit -r . -ll
      - name: Run tests
        run: pytest tests/
```

**Step 3: Final verification**
`pytest tests/`

**Step 4: Commit**
```bash
git add tests/test_api.py .github/workflows/ci.yml
git commit -m "feat: implement full CI workflow and API tests"
```
