# Issue #2640: Replay Defense Fixes - Clean Submission Pass

**Status:** ✅ COMPLETE  
**Date:** 2026-03-28  
**Test Command:** `python3 -m pytest tests/test_replay_defense.py tests/test_replay_defense_standalone.py tests/test_replay_bounty.py tests/test_fingerprint_replay.py tests/test_signed_transfer_replay.py --tb=short`

---

## Summary

Re-implemented verified replay-defense fixes in a clean clone, touching only the files necessary for the issue. All 74 tests pass.

---

## Files Modified

### 1. `node/hardware_fingerprint_replay.py`

**Changes:**
- Changed `DB_PATH` from module-level constant to dynamic `get_db_path()` function
- This ensures the database path is read from environment variables at call time, not import time
- Fixed `compute_fingerprint_hash()` to handle empty dicts correctly (returns valid hash, not empty string)

**Key Changes:**
```python
# Before:
DB_PATH = os.environ.get('RUSTCHAIN_DB_PATH') or os.environ.get('DB_PATH') or '/root/rustchain/rustchain_v2.db'

# After:
def get_db_path() -> str:
    """Get database path from environment (evaluated at call time, not import time)."""
    return os.environ.get('RUSTCHAIN_DB_PATH') or os.environ.get('DB_PATH') or '/root/rustchain/rustchain_v2.db'
```

**Rationale:** The `conftest.py` sets `DB_PATH = ":memory:"` at import time, which was causing test interference when running multiple test files together. The dynamic `get_db_path()` function ensures each test can set its own database path.

---

### 2. `tests/test_replay_bounty.py`

**Changes:**
- Updated import from `DB_PATH` to `get_db_path`

---

### 3. `tests/test_replay_defense_standalone.py`

**Changes:**
- Updated import from `DB_PATH` to `get_db_path`
- Added `autouse=True` fixture to ensure fresh database for each test
- Updated fixture to set `DB_PATH` at test runtime for isolation
- Fixed `test_empty_fingerprint_hash` to expect valid hash for empty dict (matching comprehensive test file)

---

### 4. `tests/test_replay_defense.py`

**Changes:**
- Updated import from `DB_PATH` to `get_db_path`
- Changed fixture to `autouse=True` for automatic database initialization
- Updated fixture to set `DB_PATH` at test runtime for isolation

---

## Test Results

```
======================== 74 passed, 5 warnings in 0.52s ========================

tests/test_replay_defense.py ...............................             [ 41%]
tests/test_replay_defense_standalone.py ................                 [ 63%]
tests/test_replay_bounty.py ....                                         [ 68%]
tests/test_fingerprint_replay.py .....................                   [ 97%]
tests/test_signed_transfer_replay.py ..                                  [100%]
```

### Test Breakdown

| Test File | Tests | Status |
|-----------|-------|--------|
| `test_replay_defense.py` | 31 | ✅ PASS |
| `test_replay_defense_standalone.py` | 16 | ✅ PASS |
| `test_replay_bounty.py` | 4 | ✅ PASS |
| `test_fingerprint_replay.py` | 21 | ✅ PASS |
| `test_signed_transfer_replay.py` | 2 | ✅ PASS |
| **Total** | **74** | **✅ PASS** |

---

## Bounty #2276 Requirements Verification

All three core bounty requirements are satisfied:

| Requirement | Test | Status |
|-------------|------|--------|
| Replayed fingerprint must be rejected | `test_requirement_1_replay_rejected` | ✅ SATISFIED |
| Fresh fingerprint must be accepted | `test_requirement_2_fresh_accepted` | ✅ SATISFIED |
| Modified replay (changed nonce, old data) must be rejected | `test_requirement_3_modified_replay_rejected` | ✅ SATISFIED |

---

## Integration Verification

The `/attest/submit` endpoint integration is verified:
- Import: `from hardware_fingerprint_replay import (...)`
- Check: `check_fingerprint_replay()` called before fingerprint validation
- Response: HTTP 409 with `error: "fingerprint_replay_detected"` on replay
- Record: `record_fingerprint_submission()` called after successful validation

---

## Attack Vectors Defended

| Attack Type | Defense | Status |
|-------------|---------|--------|
| Fingerprint Replay | Nonce-based fingerprint binding | ✅ Blocked |
| Modified Replay | Fingerprint hash from data (not nonce) | ✅ Blocked |
| Entropy Profile Theft | Cross-wallet collision detection | ✅ Blocked |
| Nonce Reuse | Nonce uniqueness validation | ✅ Blocked |
| Submission Flooding | Rate limiting (10/hour) | ✅ Blocked |
| Delayed Replay | 5-minute replay window | ✅ Expired |

---

## Technical Notes

### Database Path Resolution

The fix ensures proper database isolation by:
1. Using `get_db_path()` function that reads environment variables at call time
2. Setting `DB_PATH` in test fixtures at runtime, not import time
3. Using `autouse=True` fixtures to ensure fresh database for each test

### Empty Fingerprint Handling

The `compute_fingerprint_hash()` function now:
- Returns `""` for `None` input
- Returns valid SHA-256 hash for empty dict `{}`
- This ensures consistent behavior across all test files

---

## Conclusion

All acceptance criteria met:
- ✅ Combined test command passes (74 tests)
- ✅ Scope limited to necessary files only
- ✅ No unrelated line-ending churn
- ✅ Evidence documented in this file
