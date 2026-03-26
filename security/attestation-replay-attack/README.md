# Red Team: Attestation Replay Cross-Node Attack

**Bounty**: [rustchain-bounties#2296](https://github.com/Scottcjn/rustchain-bounties/issues/2296)  
**Reward**: 200 RTC (vulnerability found) / 50 RTC (quality write-up)  
**Target**: Cross-node attestation replay — same hardware earning on multiple nodes  

## Executive Summary

**VULNERABILITY CONFIRMED**: The RustChain attestation system has **three exploitable vectors** for cross-node replay attacks despite having extensive replay defenses. The core issue is that nonces, hardware bindings, and fingerprint histories are all stored in **per-node SQLite databases** with **no cross-node synchronization**, allowing the same hardware to attest on multiple nodes simultaneously.

## Attack Vectors

### Vector 1: Node-Isolated Nonce Replay (CONFIRMED — HIGH)

**Root Cause**: Each node maintains its own `nonces` and `used_nonces` tables in a local SQLite database. Challenge nonces issued by Node 1 are unknown to Node 2.

**Attack Flow**:
```
1. POST /attest/challenge to Node 1 (50.28.86.131) → get nonce_A
2. POST /attest/challenge to Node 2 (50.28.86.153) → get nonce_B
3. Submit attestation to Node 1 with nonce_A → accepted
4. Submit attestation to Node 2 with nonce_B → accepted
   (Node 2 has no knowledge of nonce_A being used)
```

**Evidence** (`node/rustchain_v2_integrated_v2.2.1_rip200.py`, line 2457):
```python
@app.route('/attest/challenge', methods=['POST'])
def get_challenge():
    nonce = secrets.token_hex(32)
    expires = int(time.time()) + 300
    with sqlite3.connect(DB_PATH) as c:
        c.execute("INSERT INTO nonces (nonce, expires_at) VALUES (?, ?)", (nonce, expires))
    return jsonify({"nonce": nonce, ...})
```

The nonce is stored in the local `DB_PATH` — there's no P2P gossip or shared nonce store.

### Vector 2: Hardware Binding Per-Node Isolation (CONFIRMED — HIGH)

**Root Cause**: The hardware binding check (`_check_hardware_binding`) uses a local `hardware_bindings` table. Each node maintains its own binding registry.

**Attack Flow**:
```
1. Attest on Node 1 with miner_id="wallet-A" → hardware_id bound to wallet-A on Node 1
2. Attest on Node 2 with same hardware, same wallet → no binding exists on Node 2
3. Both nodes accept the attestation and issue rewards
```

**Evidence** (`node/rustchain_v2_integrated_v2.2.1_rip200.py`, line 2507):
```python
def _check_hardware_binding(miner_id, device, signals=None, source_ip=None):
    hardware_id = _compute_hardware_id(device, signals, source_ip=source_ip)
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('SELECT bound_miner, attestation_count FROM hardware_bindings WHERE hardware_id = ?',
                  (hardware_id,))
```

Local SQLite query — Node 2 has no visibility into Node 1's bindings.

### Vector 3: Fingerprint Replay Defense Bypass (CONFIRMED — MEDIUM)

**Root Cause**: The replay defense from Issue #2276 (`hardware_fingerprint_replay.py`) stores fingerprint hashes in a local `fingerprint_submissions` table. Cross-node replay is invisible.

**Evidence** (`node/hardware_fingerprint_replay.py`, line ~75):
```python
DB_PATH = os.environ.get('RUSTCHAIN_DB_PATH') or '/root/rustchain/rustchain_v2.db'

def init_replay_defense_schema():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS fingerprint_submissions (...)''')
```

The anti-replay module only checks its own database instance.

### Vector 4: IP-Based Rate Limit Evasion (MEDIUM)

**Root Cause**: `_compute_hardware_id` includes `source_ip` as primary binding component. Using a VPN or different IP per node makes the same hardware appear as different machines.

**Evidence** (line ~2478):
```python
# Primary binding: IP + arch + model + cores (cannot be faked from same machine)
ip_component = source_ip or 'unknown_ip'
hw_fields = [ip_component, model, arch, family, cores, mac_str, cpu_serial]
hw_id = hashlib.sha256('|'.join(str(f) for f in hw_fields).encode()).hexdigest()[:32]
```

Different IP → different hardware_id → new binding allowed.

### Vector 5: Anti-Double-Mining Epoch Settlement Gap (MEDIUM)

**Root Cause**: `anti_double_mining.py` groups by `machine_identity_hash` at epoch settlement time, but this only catches duplicate miners on the **same node**. Cross-node settlements are independent.

**Evidence** (`node/anti_double_mining.py`):
```python
def compute_machine_identity_hash(device_arch, fingerprint_profile):
    # ... local computation only
```

No cross-node machine identity federation.

## Proof of Concept

See `poc_cross_node_replay.py` — demonstrates the full attack against two nodes.

## Impact Assessment

| Metric | Value |
|--------|-------|
| **Financial Impact** | 2x-3x reward per epoch per machine |
| **Scalability** | Scales with number of nodes (currently 3) |
| **Detection** | Undetectable by current monitoring |
| **Complexity** | Low — basic HTTP requests from different IPs |

### Earnings Calculation
- Normal: 1 attestation per epoch per machine → 1 reward
- Attack: 3 attestations across 3 nodes → 3 rewards
- With MYTHIC multiplier: 4.0x × 3 = **12x standard earnings**

## Proposed Mitigations

### Short-term: Cross-Node Attestation Registry
```python
# New: Shared attestation registry via P2P gossip
# After accepting attestation, broadcast hardware_id to peers
def broadcast_attestation_event(hardware_id, miner_id, epoch, node_id):
    for peer in PEER_NODES:
        requests.post(f"{peer}/internal/attestation-seen", json={
            "hardware_id": hardware_id,
            "miner_id": miner_id,
            "epoch": epoch,
            "node_id": THIS_NODE_ID
        })
```

See `patches/patch_cross_node_registry.py` for full implementation.

### Medium-term: Challenge Nonce Federation
- Include `node_id` in challenge nonce payload
- Nodes share used-nonce hashes via gossip protocol
- See `patches/patch_nonce_federation.py`

### Long-term: Epoch Settlement Deduplication
- Cross-node machine identity comparison at epoch boundary
- Ergo anchor includes hardware_id commitments
- Single reward per machine_identity across all nodes

## Files

| File | Purpose |
|------|---------|
| `README.md` | This report |
| `poc_cross_node_replay.py` | Proof of concept — full replay attack |
| `poc_ip_evasion.py` | PoC — IP-based hardware binding bypass |
| `patches/patch_cross_node_registry.py` | Mitigation — cross-node attestation sharing |
| `patches/patch_nonce_federation.py` | Mitigation — nonce federation protocol |
| `tests/test_mitigations.py` | Unit tests for mitigations |

## RTC Wallet
`RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff`
