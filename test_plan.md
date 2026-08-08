# RIP-310 Social Mining Protocol — Test Plan

## 1. Scope
- Verify all existing unit tests in `tests/test_rip310_social_mining.py`.
- Add test coverage for edge cases:
  - Whitespace-only comments rejection in `RewardCalculator`.
  - Floating point rounding accuracy in micro-tipping.

## 2. Remote VPS Execution Plan
- Environment: Hostinger Linux VPS (`187.124.224.227`, Ubuntu 24.04/26.04).
- Execution command: `date "+%Y-%m-%d %H:%M:%S" && pytest tests/test_rip310_social_mining.py`

## 3. Verification Criteria
- All tests in `tests/test_rip310_social_mining.py` pass cleanly (100% Green).
- No floating-point drift or assertion failures under concurrent scenarios.
