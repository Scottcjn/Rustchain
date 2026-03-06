# RustChain CI Pipeline & Test Suite Design

**Date:** 2026-02-15
**Status:** Approved

## Goal
Implement a robust CI pipeline using GitHub Actions to automate linting, type checking, security scanning, and unit testing for the RustChain project. Ensure 10+ meaningful tests cover core blockchain and hardware fingerprinting logic.

## Architecture

### 1. Test Suite (Modular Approach)
- **Framework**: `pytest`
- **Location**: `tests/` directory
- **Mocking Strategy**:
    - Use `unittest.mock` and `pytest-mock` for network and time isolation.
    - Use an in-memory SQLite database for ledger and reputation tests to ensure data persistence logic is verified without filesystem side effects.
- **Test Modules**:
    - `test_fingerprint.py`: Hardware ID generation (`_compute_hardware_id`) and fingerprint validation (`validate_fingerprint_data`).
    - `test_blockchain.py`: Slot/epoch calculations (`current_slot`) and hardware multiplier lookups (`get_time_aged_multiplier`).
    - `test_ledger.py`: Balance operations (credit, debit, transfer), address validation, and nonce replay protection.
    - `test_api.py`: Mocked responses for health, epoch, and miner list endpoints.

### 2. CI/CD Pipeline (`.github/workflows/ci.yml`)
- **Triggers**: Push to `main`, Pull Requests to `main`.
- **Jobs**:
    - **Linting**: `ruff check .` with a configuration that ignores non-critical legacy issues.
    - **Type Checking**: `mypy .` (Full repo as requested, though legacy files may need ignore comments).
    - **Security**: `bandit -r .` to detect common vulnerability patterns.
    - **Unit Tests**: `pytest tests/` with coverage reporting.
- **Failure Policy**: Block merges if any check fails.

### 3. Hardware Fingerprinting Tests
- Use a combination of **Mock Data** and **Sample Data** from the codebase.
- Verify that different hardware profiles (IPs, MACs, CPU IDs) produce unique `hardware_id` hashes.
- Test VM detection by simulating anomalous clock drift and SIMD signals.

## Data Flow
1. Developer pushes code/opens PR.
2. GitHub Actions environment initializes (Python 3.11).
3. Dependencies installed from `requirements.txt`.
4. Static analysis tools run in parallel.
5. Unit tests execute against mock hardware data and in-memory DB.
6. Results reported back to PR status checks.

## Success Criteria
- [ ] `.github/workflows/ci.yml` exists and triggers correctly.
- [ ] `ruff`, `mypy`, `bandit`, and `pytest` integrated.
- [ ] 10+ unit tests passing in CI.
- [ ] CI Status Badge added to `README.md`.
- [ ] All tests are self-contained and run under 5 minutes.
