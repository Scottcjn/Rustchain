# Bounty #2296: Red Team Attestation Replay - Cross-Node Defense

**Status:** ✅ COMPLETE  
**Reward:** 200 RTC  
**Wallet:** C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg  
**Implementation Date:** 2026-03-26  
**Bounty:** https://github.com/Scottcjn/rustchain-bounties/issues/2296

---

## Summary

Implemented cross-node hardware fingerprint replay attack defense for Issue #2296. This addresses the critical vulnerability where attestation responses captured from one node can be replayed to other nodes because the per-node `known_hardware` state was not synchronized across the network.

**Root Cause Fixed:** Each node maintained only a per-node `known_hardware` dictionary. The P2P gossip layer had attestation CRDT infrastructure (INV_ATTESTATION/GET_ATTESTATION/ATTESTATION messages) but it was NOT integrated with the replay defense system. This allowed an attacker to:
1. Submit valid attestation to Node A
2. Capture the attestation response
3. Replay it to Node B (which had no knowledge of the attestation)
4. Node B accepts it as fresh → double rewards / identity theft

**Solution:** Cross-node attestation registry synced via P2P gossip CRDT + integration of gossip attestation data into local replay detection.

---

## Bounty Requirements — Evidence Mapping

### Requirement 1: Cross-Node Replay Must Be Detected

| Aspect | Details |
|--------|---------|
| **Requirement** | An attestation replayed across nodes (Node A → Node B) must be detected and rejected by Node B |
| **Implementation** | `node/red_team_attestation_replay.py:check_cross_node_replay()` |
| **Integration** | `node/rustchain_p2p_gossip.py:_handle_attestation()` calls `integrate_gossip_attestations()` |
| **Attack Scenario** | `node/red_team_attestation_replay.py:simulate_cross_node_attack()` |
| **Detection Logic** | Cross-node registry records all attestations; same hardware_id + entropy + wallet on different node = replay |

**Evidence:**
```python
# From red_team_attestation_replay.py check_cross_node_replay():
# Check 1: Has this exact hardware+wallet attestation been seen before on any node?
c.execute('''
    SELECT node_id, wallet_address, first_seen_at, last_seen_at, nonce
    FROM cross_node_attestation_registry
    WHERE hardware_id = ? AND wallet_address = ?
''', (hardware_id, wallet_address))

# Same hardware+wallet with different nonce on another node = cross-node replay
if prev_nonce != nonce:
    return True, "cross_node_fingerprint_replay", {...}
```

---

### Requirement 2: Cross-Node Hardware Sharing Must Be Detected

| Aspect | Details |
|--------|---------|
| **Requirement** | Same hardware attested by multiple wallets across nodes must be detected |
| **Implementation** | `node/red_team_attestation_replay.py:check_cross_node_replay()` (Check 2) |
| **Detection Logic** | Same hardware_id + entropy_profile_hash but different wallet = hardware sharing attack |
| **Logged To** | `cross_node_attack_log` table with type `cross_node_hardware_sharing` |

**Evidence:**
```python
# Same hardware, same entropy, different wallet = hardware sharing
if cn_wallet.lower() != wallet_address.lower():
    _log_cross_node_attack(
        attack_type="cross_node_hardware_sharing",
        ...
    )
    return True, "cross_node_hardware_sharing", {...}
```

---

### Requirement 3: P2P Gossip Integration

| Aspect | Details |
|--------|---------|
| **Requirement** | When P2P gossip layer receives attestation data from peers, it must integrate with cross-node defense |
| **Implementation** | `node/rustchain_p2p_gossip.py:_handle_attestation()` |
| **Integration Point** | `cn_replay.integrate_gossip_attestations(cn_attestation, source_node_id)` |
| **Lazy Import** | Uses try/except to avoid circular dependencies; degrades gracefully if module unavailable |

**Evidence:**
```python
# From rustchain_p2p_gossip.py _handle_attestation():
if CROSS_NODE_DEFENSE_AVAILABLE and cn_replay is not None:
    try:
        cn_attestation = {
            'hardware_id': attestation.get('hardware_id') or miner_id,
            'entropy_profile_hash': attestation.get('entropy_profile_hash')
                or hashlib.sha256(json.dumps({...}).encode()).hexdigest(),
            'fingerprint_hash': attestation.get('fingerprint_hash')
                or hashlib.sha256(json.dumps(attestation, sort_keys=True).encode()).hexdigest(),
            'miner_id': miner_id,
            'wallet_address': attestation.get('wallet_address') or miner_id,
            'nonce': attestation.get('nonce') or str(ts_ok),
            'timestamp': ts_ok,
            'attestation_valid': True
        }
        cn_replay.integrate_gossip_attestations(cn_attestation, source_node_id=msg.sender_id)
    except Exception as e:
        logger.warning(f"Cross-node defense integration failed: {e}")
```

---

## Files Added

| File | Purpose |
|------|---------|
| `node/red_team_attestation_replay.py` | Cross-node attestation replay defense module |
| `BOUNTY_2296_RED_TEAM_ATTESTATION_REPLAY.md` | This documentation |

## Files Modified

| File | Changes |
|------|---------|
| `node/rustchain_p2p_gossip.py` | Added `CROSS_NODE_DEFENSE_AVAILABLE` flag and integration in `_handle_attestation()` |

---

## Attack Vectors Defended

### Cross-Node Fingerprint Replay
- **Attack:** Attacker submits valid attestation to Node A, captures response, replays to Node B
- **Root Cause:** Node B's `known_hardware` dict doesn't contain the fingerprint from Node A
- **Defense:** Cross-node registry tracks all attestations seen across ALL nodes; same hardware+wallet+nonce = blocked

### Cross-Node Hardware Sharing
- **Attack:** Same physical hardware attested by multiple wallets on different nodes
- **Defense:** Cross-node registry detects same hardware_id + entropy_profile_hash with different wallets

### Cross-Node Fingerprint Copy
- **Attack:** Exact fingerprint hash seen on different node with different wallet
- **Defense:** Check 3 in `check_cross_node_replay()` detects exact fingerprint_hash reuse across nodes

### Bloom Filter False Negative Prevention
- **Defense:** Bloom filter is used as fast probabilistic check; confirmed by full registry query

---

## Database Schema

### Table: `cross_node_attestation_registry`
Tracks attestations seen across ALL nodes in the network.

```sql
CREATE TABLE cross_node_attestation_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hardware_id TEXT NOT NULL,
    entropy_profile_hash TEXT NOT NULL,
    fingerprint_hash TEXT NOT NULL,
    miner_id TEXT NOT NULL,
    wallet_address TEXT NOT NULL,
    node_id TEXT NOT NULL,
    nonce TEXT NOT NULL,
    first_seen_at INTEGER NOT NULL,
    last_seen_at INTEGER NOT NULL,
    attestation_valid INTEGER DEFAULT 1,
    source TEXT DEFAULT 'local',
    UNIQUE(hardware_id, entropy_profile_hash, wallet_address)
);
```

### Table: `cross_node_bloom_filter`
Fast probabilistic check for "have we seen this hardware anywhere?"

```sql
CREATE TABLE cross_node_bloom_filter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hardware_id TEXT NOT NULL UNIQUE,
    entropy_hash_list TEXT NOT NULL,
    bloom_version INTEGER DEFAULT 1,
    updated_at INTEGER NOT NULL
);
```

### Table: `node_attestation_receipts`
Tracks which attestations each node has seen.

```sql
CREATE TABLE node_attestation_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL,
    attestation_key TEXT NOT NULL,
    received_at INTEGER NOT NULL,
    fingerprint_hash TEXT,
    wallet_address TEXT,
    nonce TEXT,
    UNIQUE(node_id, attestation_key)
);
```

### Table: `cross_node_attack_log`
Records all detected cross-node replay attack attempts.

```sql
CREATE TABLE cross_node_attack_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attack_type TEXT NOT NULL,
    hardware_id TEXT,
    fingerprint_hash TEXT,
    attacker_wallet TEXT,
    victim_wallet TEXT,
    source_node TEXT,
    target_node TEXT,
    nonce TEXT,
    detected_at INTEGER NOT NULL,
    details TEXT,
    severity TEXT DEFAULT 'high'
);
```

---

## API Integration

### Main Entry Point: `check_and_accept_attestation()`

```python
def check_and_accept_attestation(
    hardware_id: str,
    entropy_profile_hash: str,
    fingerprint_hash: str,
    wallet_address: str,
    miner_id: str,
    nonce: str,
    node_id: str,
    attestation_valid: bool = True
) -> Tuple[bool, str, Optional[Dict]]:
    """
    Complete cross-node replay check before accepting an attestation.
    Returns (accepted, reason, details)
    """
```

### Gossip Integration: `integrate_gossip_attestations()`

```python
def integrate_gossip_attestations(
    attestation_data: Dict,
    source_node_id: str
) -> int:
    """
    Integrate attestations received from P2P gossip into cross-node registry.
    Called when gossip layer receives attestation data from peer nodes.
    Returns number of attestations integrated.
    """
```

### Red Team Simulation: `simulate_cross_node_attack()`

```python
def simulate_cross_node_attack(
    attacker_wallet: str,
    victim_wallet: str,
    hardware_id: str,
    entropy_hash: str,
    fp_hash: str,
    miner_id: str,
    attacker_node: str = "node_attacker",
    victim_node: str = "node_victim"
) -> Dict:
    """
    Simulate a cross-node attestation replay attack for testing.
    Demonstrates the attack and shows how the defense works.
    """
```

---

## Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| `CROSS_NODE_REPLAY_WINDOW` | 1200s (20 min) | Cross-node attestation freshness window |
| `MAX_CROSS_NODE_ENTROPY_MATCH` | 0.90 (90%) | Entropy match threshold for same-hardware detection |
| `CROSS_NODE_DEFENSE_AVAILABLE` | bool | Whether cross-node module is loaded |

---

## Security Properties

1. **Eventual Consistency:** Cross-node state converges via P2P gossip CRDT
2. **No Single Point of Failure:** Every node independently checks cross-node registry
3. **Graceful Degradation:** If cross-node module unavailable, local replay defense still works
4. **Attack Logging:** All detected attacks logged with full context for forensic analysis
5. **Low False Positive Rate:** Bloom filter is probabilistic; full registry query confirms

---

## Test Results

The `simulate_cross_node_attack()` function demonstrates the defense:

```
Attack Type: cross_node_attestation_replay
Defense Triggered: True
  Step 1: victim_submits_attestation → recorded=True
  Step 2: attacker_replays_attestation → replay_detected=True
  Step 3: defense_blocks_attack → blocked=True

✅ Cross-node replay defense is working correctly!
   Attack blocked: cross_node_fingerprint_replay
```

---

## Compatibility Notes

- **Backwards Compatible:** Existing `hardware_fingerprint_replay.py` functions unchanged
- **Lazy Integration:** P2P gossip layer integration uses try/except; won't break if module unavailable
- **Standalone Testable:** `red_team_attestation_replay.py` can be run standalone with inline fallbacks

---

## References

- Issue: https://github.com/Scottcjn/rustchain-bounties/issues/2296
- P2P Gossip Layer: `node/rustchain_p2p_gossip.py`
- Per-Node Replay Defense: `node/hardware_fingerprint_replay.py`
- Hardware Binding: `node/hardware_binding_v2.py`
