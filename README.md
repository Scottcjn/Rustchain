# RustChain Security Audit Findings - #2867

**Total Reward**: 150 RTC (2×50 + 2×25 + 1×50)

## Vulnerability 1: Mempool DoS via Zero-Value Outputs (25 RTC)

**File**: `node/utxo_db.py`, `mempool_admit()` function

**Risk**: Medium

**Issue**: 
The mempool admission check rejects empty outputs but does not check for zero-value outputs (value_nrtc = 0). This allows attackers to create transactions that lock UTXOs for 1 hour without being mineable.

**Impact**:
- UTXOs locked for 1 hour (DoS)
- Attacker can repeatedly lock multiple UTXOs

**Fix**:
Add validation: `if val <= 0: return False`

---

## Vulnerability 2: Fee Manipulation via Signature Malleability (50 RTC)

**File**: `node/utxo_endpoints.py`, `utxo_transfer()` function

**Risk**: High

**Issue**:
The code attempts to fix signature malleability by including fee in signed data (fix #2202), but falls back to legacy format (without fee) if new format verification fails. This allows attackers to modify the fee field without invalidating the signature.

**Impact**:
- User funds theft (fee manipulation)
- Attacker can increase fee by 10000x
- User only authorized 0.0001 RTC, actual charge 1.0 RTC

**Fix**:
Remove legacy signature fallback. Only accept new format with fee included.

---

## Vulnerability 3: CRDT State Poisoning via Balance Merge (50 RTC)

**File**: `node/rustchain_p2p_gossip.py`, `_handle_state()` function

**Risk**: High

**Issue**:
Phase D.3 attempts to scope balance PN-counter entries to sender's namespace, but has a logic error that allows arbitrary balance injection. The code checks `node_map.get(sender)` but sender is the attacker's node_id, allowing injection of any miner's balance.

**Impact**:
- Arbitrary balance manipulation
- Attacker can inject millions of RTC to any miner
- Consensus based on poisoned state

**Fix**:
Properly scope increments/decrements to sender's own contributions only.

---

## Vulnerability 4: Cloud Metadata Endpoint Bypass (25 RTC)

**File**: `miners/windows/fingerprint_checks.py`, `check_anti_emulation()` function

**Risk**: Medium

**Issue**:
The cloud metadata endpoint check (169.254.169.254) has only 1-second timeout. Attackers can configure local proxy to respond within 1 second with forged response, bypassing cloud detection.

**Impact**:
- VM/cloud detection bypass
- Attackers can mine from cloud instances
- Undermines Proof-of-Antiquity mechanism

**Fix**:
- Increase timeout to 5+ seconds
- Add response validation
- Use multiple detection methods

---

## Proof-of-Concept Files

- `vuln1_poc.py` - Mempool DoS demonstration
- `vuln2_poc.py` - Fee manipulation demonstration  
- `vuln3_poc.py` - CRDT state poisoning demonstration
- `vuln4_poc.py` - Cloud metadata bypass demonstration

## Severity Assessment

| Vuln | Severity | Impact | Likelihood | Reward |
|------|----------|--------|------------|--------|
| 1 | Medium | DoS (1hr UTXO lock) | High | 25 RTC |
| 2 | High | Funds theft | High | 50 RTC |
| 3 | High | Balance manipulation | High | 50 RTC |
| 4 | Medium | VM detection bypass | Medium | 25 RTC |

**Total**: 150 RTC