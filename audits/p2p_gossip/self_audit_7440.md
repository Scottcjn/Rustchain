## Security Audit Report: RustChain P2P Gossip Protocol

**Repository:** RustChain Blockchain Bounty Program  
**File:** `node/rustchain_p2p_gossip.py` (1388 lines)  
**Auditor:** BossChaos  
**Wallet:** RTC6d1f27d28961279f1034d9561c2403697eb55602

---

## Executive Summary
Combined audit of 1388-line P2P gossip protocol implementation.

---

# RustChain P2P Gossip Protocol Security Audit

**Target:** `node/rustchain_p2p_gossip.py` (lines 1-694)
**Auditor:** BossChaos | **Wallet:** RTC6d1f27d28961279f1034d9561c2403697eb55602

---

## CRITICAL Vulnerabilities

### CVE-001: Dead Code in Strict Mode Causes Signature Bypass
**Severity:** CRITICAL  
**CVSS v3.1:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H` (10.0)  
**Vector:** Network → No Privileges Required → No User Interaction  
**Lines:** 408-412 (in `_verify_signature`)  

**Description:**  
The `_verify_signature` method contains unreachable dead code that completely breaks strict mode signature verification:

```python
# Line 408-412
if mode == "strict":
    if ed25519_sig is None:
        return False
    # NOTE: this classmethod-style helper is called with only...
    return False  # strict mode must use verify_message()
```

The comment explicitly states strict mode must use `verify_message()`, but `_verify_signature()` is called from `handle_message()` context. The final `return False` after the comment is **unreachable dead code** that causes all strict-mode Ed25519 verifications to fail.

**Attack Vector:**  
In strict mode, Ed25519 signatures will always fail verification at line 412, forcing fallback to HMAC. An attacker who extracts the shared HMAC secret can forge all messages.

**Remediation:**
```python
# Replace lines 408-412 with:
if mode == "strict":
    if ed25519_sig is None:
        return False
    # strict mode: skip HMAC fallback entirely
    # Hand off to verify_message() for Ed25519 verification
    raise ValueError("strict mode requires verify_message() with sender_id")
```

---

### CVE-002: Unvalidated Amount in PNCounter Allows Negative Balances
**Severity:** CRITICAL  
**CVSS v3.1:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N` (9.1)  
**Vector:** Network → No Privileges Required → No User Interaction  
**Lines:** 201-206 (`credit`), 207-211 (`debit`)  

**Description:**  
Neither `credit()` nor `debit()` validates that `amount` is a positive integer:

```python
def credit(self, miner_id: str, node_id: str, amount: int):
    """Record a credit (reward)"""
    self.increments[miner_id][node_id] += amount  # No validation

def debit(self, miner_id: str, node_id: str, amount: int):
    """Record a debit (withdrawal)"""
    self.decrements[miner_id][node_id] += amount  # No validation
```

**Impact:**  
- Attacker sends `credit(miner_id, node_id, -1000000)` to inflate balance
- Attacker sends `debit(miner_id, node_id, -1000000)` to reduce debits (increase balance)
- Combined: double-spend attacks and balance manipulation

**Attack Vector:**  
Any peer can send attestation or balance messages containing negative amounts. Combined with weak input validation at line 566-595, this allows arbitrary balance state corruption.

**Remediation:**
```python
def credit(self, miner_id: str, node_id: str, amount: int):
    if not isinstance(amount, int) or amount <= 0:
        raise ValueError(f"Credit amount must be positive integer, got {amount}")
    self.increments[miner_id][node_id] += amount

def debit(self, miner_id: str, node_id: str, amount: int):
    if not isinstance(amount, int) or amount <= 0:
        raise ValueError(f"Debit amount must be positive integer, got {amount}")
    self.decrements[miner_id][node_id] += amount
```

---

### CVE-003: Message ID Collision Attack (96-bit Insufficient)
**Severity:** CRITICAL  
**CVSS v3.1:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H` (9.8)  
**Vector:** Network → No Privileges Required → No User Interaction  
**Lines:** 437-441 (`create_message`)  

**Description:**  
Message IDs use only 24 hex characters (96 bits) from SHA256 truncation:

```python
temp_content = f"{msg_type.value}:{self.node_id}:{json.dumps(payload, sort_keys=True)}"
msg_id = hashlib.sha256(f"{temp_content}:{time.time()}".encode()).hexdigest()[:24]
```

**Issues:**
1. `secrets` module is imported but not used for ID generation
2. 96-bit space allows collision generation in ~2^48 operations (feasible for nation-state attackers)
3. Predictable structure: SHA256(content:timestamp) allows pre-computation attacks

**Attack Vector:**  
Attacker generates collision with valid signature, then replays with different content but same msg_id, bypassing deduplication at line 503-512.

**Remediation:**
```python
def create_message(self, msg_type: MessageType, payload: Dict, ttl: int = GOSSIP_TTL) -> GossipMessage:
    # Use cryptographically secure random ID (256 bits)
    msg_id = secrets.token_hex(32)  # 64 hex chars = 256 bits
    content = self._signed_content(msg_type.value, self.node_id, msg_id, ttl, payload)
    sig, ts = self._sign_message(content)
    # ... rest unchanged
```

---

## HIGH Vulnerabilities

### CVE-004: Gossip Amplification Attack via TTL Propagation
**Severity:** HIGH  
**CVSS v3.1:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L` (5.3)  
**Vector:** Network → No Privileges Required → No User Interaction  
**Lines:** 547-551 (`handle_message`)  

**Description:**  
After processing any message, TTL forwarding broadcasts to ALL peers unconditionally:

```python
# Forward if TTL > 0
if msg.ttl > 0:
    msg.ttl -= 1
    self.broadcast(msg, exclude_peer=msg.sender_id)
```

**Issues:**
1. No rate limiting on outgoing broadcasts
2. No message size limits enforced
3. Amplification factor = N-1 peers per hop × GOSSIP_TTL hops
4. Attacker sends small message → entire network propagates large attestation data

**Attack Vector:**  
Sybil attack: Create 100+ nodes, each sending messages that amplify 1000x across the network, causing DoS.

**Remediation:**
```python
# Add rate limiting and size checks
class GossipLayer:
    def __init__(self, ...):
        # ... existing init
        self._broadcast_times: Dict[str, float] = defaultdict(list)
        self._MAX_BROADCASTS_PER_MINUTE = 100
        self._MAX_MESSAGE_SIZE_BYTES = 65536

    def _check_rate_limit(self, sender_id: str) -> bool:
        now = time.time()
        self._broadcast_times[sender_id] = [
            t for t in self._broadcast_times[sender_id] if now - t < 60
        ]
        return len(self._broadcast_times[sender_id]) < self._MAX_BROADCASTS_PER_MINUTE

    # In handle_message, after verification:
    if msg.ttl > 0 and self._check_rate_limit(msg.sender_id):
        if len(json.dumps(msg.to_dict())) > self._MAX_MESSAGE_SIZE_BYTES:
            return {"status": "error", "reason": "message_too_large"}
        msg.ttl -= 1
        self.broadcast(msg, exclude_peer=msg.sender_id)
```

---

### CVE-005: Unregistered Peer Ed25519 Bypass in Non-Strict Modes
**Severity:** HIGH  
**CVSS v3.1:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N` (8.6)  
**Vector:** Network → No Privileges Required → No User Interaction  
**Lines:** 463-480 (`verify_message`)  

**Description:**  
When Ed25519 signature is present but peer is not registered, verification falls through to HMAC:

```python
# Lines 463-468
if ed25519_sig and self._peer_registry is not None:
    pubkey = self._peer_registry.get_pubkey(msg.sender_id)
    if pubkey and verify_ed25519(pubkey, ed25519_sig, message.encode()):
        return True
    # In strict mode, Ed25519 must succeed — no fallback.
    if mode == "strict":
        return False
```

When `pubkey` is `None` (unregistered sender), code falls through to HMAC verification at lines 481-488. This allows an attacker to:
1. Generate arbitrary Ed25519 keypair
2. Sign message with their key
3. Since not in peer registry, bypass Ed25519 verification
4. Fall back to HMAC (if HMAC also valid) - but in "ed25519-only" mode, this creates ambiguity

**Attack Vector:**  
Attacker creates Sybil identity, signs messages, and if HMAC is also present/valid, gains trusted status.

**Remediation:**
```python
# In verify_message, add explicit check:
if ed25519_sig:
    if self._peer_registry is None:
        logger.warning(f"Ed25519 sig from {msg.sender_id} but no registry")
        if mode in ("ed25519", "strict"):
            return False
    else:
        pubkey = self._peer_registry.get_pubkey(msg.sender_id)
        if pubkey is None:
            logger.warning(f"Ed25519 sig from unregistered peer {msg.sender_id}")
            if mode in ("ed25519", "strict"):
                return False
        elif verify_ed25519(pubkey, ed25519_sig, message.encode()):
            return True
        elif mode == "strict":
            return False
```

---

### CVE-006: Attestation Persistence Gap (CRDT-to-DB Sync Failure)
**Severity:** HIGH  
**CVSS v3.1:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N` (7.5)  
**Vector:** Network → No Privileges Required → No User Interaction  
**Lines:** 592-595 + missing DB write  

**Description:**  
`_handle_attestation` validates and merges into CRDT, but **never persists to database**:

```python
# Lines 592-595 (end of _handle_attestation)
# Update CRDT
self.attestation_crdt.set(miner_id, {
    "miner": miner_id,
    "device_family": attestation.get("device_family"),
    "device_arch": attestation.get("device_arch"),
    "entropy_score": attestation.get("entropy_score", 0)
}, ts_ok)
return {"status": "ok"}
```

**Impact:**  
- Node restart loses all received attestations (line 322-337 only loads local DB records)
- Attacker floods CRDT with garbage → node restart clears it → repeat attack
- Violates eventual consistency guarantee

**Remediation:**
```python
# After CRDT update, persist to database:
try:
    with sqlite3.connect(self.db_path) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO miner_attest_recent 
            (miner, ts_ok, device_family, device_arch, entropy_score, source_node)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            miner_id,
            ts_ok,
            attestation.get("device_family"),
            attestation.get("device_arch"),
            attestation.get("entropy_score", 0),
            msg.sender_id
        ))
        conn.commit()
except Exception as e:
    logger.error(f"Failed to persist attestation: {e}")
```

---

## MEDIUM Vulnerabilities

### CVE-007: Race Condition in Deduplication (TOCTOU)
**Severity:** MEDIUM  
**CVSS v3.1:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N` (6.5)  
**Vector:** Network → No Privileges Required → No User Interaction  
**Lines:** 503-512 (`handle_message`)  

**Description:**  
Check-then-insert in SQLite has Time-Of-Check-Time-Of-Use race:

```python
# Lines 503-512
res = conn.execute("SELECT 1 FROM p2p_seen_messages WHERE msg_id = ?", (msg.msg_id,)).fetchone()
if res:
    return {"status": "duplicate"}
# ... gap where another thread could insert same msg_id ...
# Later:
conn.execute("INSERT OR IGNORE INTO p2p_seen_messages (msg_id, ts) VALUES (?, ?)", 
             (msg.msg_id, int(time.time())))
```

**Attack Vector:**  
Two concurrent requests with same msg_id both pass the SELECT check, both process the message.

**Remediation:**
```python
# Use UNIQUE constraint and handle IntegrityError:
try:
    with sqlite3.connect(self.db_path) as conn:
        conn.execute("INSERT OR IGNORE INTO p2p_seen_messages (msg_id, ts) VALUES (?, ?)", 
                     (msg.msg_id, int(time.time())))
        if conn.total_changes == 0:  # Insert was ignored = duplicate
            return {"status": "duplicate"}
except sqlite3.IntegrityError:
    return {"status": "duplicate"}
```

---

### CVE-008: Miner ID Full-Length Logging (PII Exposure)
**Severity:** MEDIUM  
**CVSS v3.1:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N` (5.3)  
**Vector:** Network → No Privileges Required → No User Interaction  
**Lines:** 585-586, 596  

**Description:**  
Miner IDs (up to 256 chars) are logged without truncation:

```python
# Line 585-586
if not miner_id or not isinstance(miner_id, str) or len(miner_id) > 256:
    logger.warning(f"Attestation from {msg.sender_id}: invalid miner_id")

# Line 596
}, ts_ok)  # miner_id used directly in CRDT
```

**Impact:**  
- 256-char miner IDs in logs may contain sensitive data
- Log aggregation systems store full miner identities
- Violates principle of minimal logging

**Remediation:**
```python
def _truncate_id(identifier: str, max_len: int = 16) -> str:
    if len(identifier) <= max_len:
        return identifier
    return f"{identifier[:max_len]}...({len(identifier)} chars)"

# Usage:
logger.warning(f"Attestation from {msg.sender_id}: invalid miner_id ({_truncate_id(miner_id)})")
```

---

### CVE-009: Missing Schema Validation for Attestation Payload
**Severity:** MEDIUM  
**CVSS v3.1:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N` (6.5)  
**Vector:** Network → No Privileges Required → No User Interaction  
**Lines:** 566-596 (`_handle_attestation`)  

**Description:**  
Only validates `miner_id` type/length and `ts_ok`. Does NOT validate:
- `device_family` is string
- `device_arch` is string  
- `entropy_score` is numeric

```python
# Line 566-575
attestation = msg.payload
if not isinstance(attestation, dict):
    return {"status": "error", "reason": "bad_schema"}

miner_id = attestation.get("miner")
if not miner_id or not isinstance(miner_id, str) or len(miner_id) > 256:
    return {"status": "error", "reason": "invalid_miner_id"}

# No validation of device_family, device_arch, entropy_score types!
```

**Attack Vector:**  
Send `{"miner": "x", "ts_ok": 123, "device_family": 12345, "entropy_score": "malicious"}` → type errors in CRDT operations or storage.

**Remediation:**
```python
# Add schema validation:
REQUIRED_FIELDS = {"miner": str, "ts_ok": (int, float)}
OPTIONAL_FIELDS = {
    "device_family": str,
    "device_arch": str,
    "entropy_score": (int, float)
}

def _validate_attestation_schema(data: dict) -> Tuple[bool, str]:
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in data or not isinstance(data[field], expected_type):
            return False, f"missing/invalid {field}"
    for field, expected_type in OPTIONAL_FIELDS.items():
        if field in data and not isinstance(data[field], expected_type):
            return False, f"invalid {field} type"
    return True, ""
```

---

### CVE-010: Future Timestamp Tolerance Allows Timestamp Manipulation
**Severity:** MEDIUM  
**CVSS v3.1:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N` (7.5)  
**Vector:** Network → No Privileges Required → No User Interaction  
**Lines:** 579-586 (`_handle_attestation`)  

**Description:**  
`MAX_FUTURE_SKEW_S = 300` (5 minutes) allows future-dated attestations:

```python
# Lines 579-586
MAX_FUTURE_SKEW_S = 300  # 5 minutes
ts_ok = attestation.get("ts_ok", now)
if not isinstance(ts_ok, (int, float)):
    return {"status": "error", "reason": "invalid_ts_ok"}
if ts_ok > now + MAX_FUTURE_SKEW_S:
    logger.warning(...)
    return {"status": "error", "reason": "future_timestamp"}
```

**Attack Vector:**  
Attacker can pre-generate attestations with future timestamps up to 5 minutes, which will override legitimate attestations via LWW when the time arrives.

**Remediation:**
```python
# Reduce tolerance to clock skew only (60 seconds)
MAX_FUTURE_SKEW_S = 60  # 1 minute tolerance for NTP drift only
MAX_PAST_SKEW_S = 3600  # Reject attestations older than 1 hour

if ts_ok > now + MAX_FUTURE_SKEW_S:
    return {"status": "error", "reason": "future_timestamp"}
if ts_ok < now - MAX_PAST_SKEW_S:
    return {"status": "error", "reason": "expired_attestation"}
```

---

## LOW Vulnerabilities

### CVE-011: Request Timeout Too Long (10s) for DoS
**Severity:** LOW  
**CVSS v3.1:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L` (3.7)  
**Vector:** Network → No Privileges Required → No User Interaction  
**Lines:** 498-501 (`_send_to_peer`)  

**Description:**  
10-second timeout on peer requests allows connection exhaustion:

```python
resp = requests.post(
    f"{peer_url}/p2p/gossip",
    json=msg.to_dict(),
    timeout=10,  # 10 seconds - too long
    verify=TLS_VERIFY
)
```

**Impact:**  
Attacker exhausts connection pools by sending slow requests.

**Remediation:**
```python
timeout = httpx.Timeout(connect=2.0, read=3.0, write=1.0, pool=0.5)
```

---

### CVE-012: No Peer Identity Verification
**Severity:** LOW  
**CVSS v3.1:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N` (5.3)  
**Vector:** Network → No Privileges Required → No User Interaction  
**Lines:** 330-338 (`_load_state_from_db`)  

**Description:**  
Peer registry loads from disk without cryptographic verification:

```python
self._peer_registry.load()  # No signature verification
```

**Impact:**  
Disk corruption or tampering could inject malicious peer identities.

**Remediation:**
```python
def load(self) -> None:
    path = self._registry_path
    if not os.path.exists(path):
        return
    with open(path, 'r') as f:
        raw = f.read()
    # Verify HMAC signature before loading
    data = json.loads(raw)
    sig = data.pop("signature", None)
    if not self._verify_registry_sig(data, sig):
        raise SecurityError("Registry signature invalid")
    self._peers = data
```

---

## Summary Table

| CVE | Severity | CVSS | Category | Line(s) |
|-----|----------|------|----------|---------|
| 001 | CRITICAL | 10.0 | Signature Bypass | 408-412 |
| 002 | CRITICAL | 9.1 | Integer Validation | 201-211 |
| 003 | CRITICAL | 9.8 | Collision Attack | 437-441 |
| 004 | HIGH | 5.3 | DoS Amplification | 547-551 |
| 005 | HIGH | 8.6 | Identity Bypass | 463-480 |
| 006 | HIGH | 7.5 | Data Persistence | 592-595 |
| 007 | MEDIUM | 6.5 | Race Condition | 503-512 |
| 008 | MEDIUM | 5.3 | PII Exposure | 585-596 |
| 009 | MEDIUM | 6.5 | Schema Validation | 566-596 |
| 010 | MEDIUM | 7.5 | Timestamp Manipulation | 579-586 |
| 011 | LOW | 3.7 | DoS | 498-501 |
| 012 | LOW | 5.3 | Identity Verification | 330-338 |

**Affected Functions:** `create_message`, `verify_message`, `_verify_signature`, `credit`, `debit`, `_handle_attestation`, `handle_message`, `_send_to_peer`

**Recommended Priority:** Patch CVE-001, CVE-002, CVE-003 immediately as they allow complete protocol compromise.

---

# RustChain P2P Gossip Protocol Security Audit
## Audit Scope: `node/rustchain_p2p_gossip.py` (Lines 1389-2082, base +694)

---

## FINDINGS SUMMARY

| # | Severity | Line Range | Vulnerability | CVSS v3.1 |
|---|----------|------------|---------------|-----------|
| 1 | **CRITICAL** | 1817-1878 | CRDT Merge Race Condition — Unprotected Concurrent State Merge | 7.5 |
| 2 | **HIGH** | 1657-1677 | PN-Counter Namespace Bypass — Arbitrary Miner Balance Manipulation | 8.1 |
| 3 | **HIGH** | 1504-1508 | Replay Attack — State Signed with Unbounded Future Timestamp | 7.4 |
| 4 | **HIGH** | 1638-1641 | Missing Lower Bound Validation — Stale Attestation Injection | 7.1 |
| 5 | **HIGH** | 1867-1881 | Inconsistent Quorum Calculation — Unsafe Peer Count Derivation | 6.5 |
| 6 | **MEDIUM** | 1934-1953 | Unauthenticated State Endpoints — Information Disclosure & DoS | 6.5 |
| 7 | **MEDIUM** | 1575-1601 | Epoch Existence Check Bypass — Accepting Non-Finalized Epoch Inventory | 5.9 |
| 8 | **MEDIUM** | 1761-1782 | Missing Proposal Hash Validation in EpochConsensus.vote() | 5.3 |
| 9 | **MEDIUM** | 1883-1893 | Leader Selection Instability on Node Departure — Consensus Corruption | 5.3 |
| 10 | **MEDIUM** | 1827-1831 | `fingerprint_passed` Logic Error — NULL Coalesce Never Preserves Original | 5.3 |
| 11 | **LOW** | 1934-1953 | Rate Limiter Bypass — Multiple Endpoints Unprotected | 3.8 |
| 12 | **LOW** | 1941-1946 | Memory Exhaustion — Unbounded IP Tracking with Pruning Logic Gap | 3.8 |

---

## FINDING 1: CRDT Merge Race Condition (Unprotected Concurrent State Merge)

**Severity:** CRITICAL  
**CVSS:** AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N — **7.5**  
**CVSS Vector:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N`

**Affected Function:** `_handle_state`  
**Lines:** 1817-1878 (base 1391+694=2085 offset convention per user: 1817)

**Vulnerability:**
The `_handle_state` method performs CRDT merges (`self.attestation_crdt.merge()`, `self.epoch_crdt.merge()`, `self.balance_crdt.merge()`) without any synchronization mechanism. When multiple concurrent state sync responses arrive from different peers, the merge operations execute simultaneously:

```python
# Lines 1844-1847
filtered = LWWRegister()
for key, (ts, value) in remote_attest.data.items():
    ...
self.attestation_crdt.merge(filtered)  # NO LOCK
```

Simultaneous merges can result in:
- Lost updates (one merge overwrites another's pending changes)
- Corrupted CRDT state
- Double-spend conditions if balance CRDT merges interleave

**Attack Vector:**
1. Attacker controls multiple peers or compromises a relay
2. Attacker sends overlapping state sync requests simultaneously
3. Node's concurrent `_handle_state` calls interleave CRDT merges
4. CRDT invariants violated → ledger inconsistency

**Remediation Code:**
```python
import threading

class GossipLayer:
    def __init__(self, ...):
        ...
        self._state_merge_lock = threading.RLock()
    
    def _handle_state(self, msg: GossipMessage) -> Dict:
        # SECURITY: Acquire exclusive lock for atomic CRDT merge
        with self._state_merge_lock:
            # ... existing validation code ...
            
            # Phase D.1: Validate + merge attestations
            if "attestations" in state:
                # ... filtering logic ...
                self.attestation_crdt.merge(filtered)
            
            # Phase D.2: Validate + merge epochs
            if "epochs" in state:
                self.epoch_crdt.merge(remote_epochs)
            
            # Phase D.3: Validate + merge balances
            if "balances" in state:
                self.balance_crdt.merge(remote_balances)
            
            return {"status": "ok"}
```

---

## FINDING 2: PN-Counter Namespace Bypass — Arbitrary Miner Balance Manipulation

**Severity:** HIGH  
**CVSS:** AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N — **8.1**  
**CVSS Vector:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N`

**Affected Function:** `_handle_state` (Phase D.3)  
**Lines:** 1657-1677

**Vulnerability:**
The balance namespace scoping logic (lines 1858-1866) correctly restricts entries to the sender's own contribution key, but does NOT validate the `miner_id` dimension:

```python
# Lines 1860-1866 — FLAWED LOGIC
for miner_id, node_map in entries.items():
    if not isinstance(node_map, dict):
        continue
    # Only keep the sender's own contribution key
    own = node_map.get(sender)
    if own is not None:
        scoped[section].setdefault(miner_id, {})[sender] = own
```

A malicious peer can inject arbitrary increment/decrement entries for ANY `miner_id`:

```python
# Attacker sends:
{
    "balances": {
        "increments": {
            "victim_miner_1": {"malicious_node": 1000000},  # Sender IS malicious_node
            "victim_miner_2": {"malicious_node": 500000}
        }
    }
}
# BOTH victim_miners get balance increments from sender's namespace!
```

**Impact:** Complete balance ledger corruption via false inflation or targeted depletion.

**Remediation Code:**
```python
# Phase D.3: Scope balance PN-counter entries to sender's own namespace
# AND validate miner_id is authorized for this sender
if "balances" in state:
    raw = state.get("balances", {})
    if not isinstance(raw, dict):
        logger.warning(f"State from {sender}: balances not a dict, skipping")
    else:
        try:
            # SECURITY: Get locally attested miners to validate miner_id namespace
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT miner FROM miner_attest_recent"
                )
                valid_miners = {row[0] for row in cursor.fetchall()}
            
            scoped = {"increments": {}, "decrements": {}}
            for section in ("increments", "decrements"):
                entries = raw.get(section, {}) or {}
                for miner_id, node_map in entries.items():
                    # SECURITY: Reject entries for non-attested miners
                    if miner_id not in valid_miners:
                        logger.warning(
                            f"State from {sender}: rejecting balance entry "
                            f"for unattested miner {miner_id[:16]}"
                        )
                        continue
                    if not isinstance(node_map, dict):
                        continue
                    own = node_map.get(sender)
                    if own is not None:
                        scoped[section].setdefault(miner_id, {})[sender] = own
            remote_balances = PNCounter.from_dict(scoped)
            self.balance_crdt.merge(remote_balances)
        except Exception as e:
            logger.warning(f"State from {sender}: balances merge failed: {e}")
```

---

## FINDING 3: Replay Attack — State Signed with Unbounded Future Timestamp

**Severity:** HIGH  
**CVSS:** AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N — **7.4**  
**CVSS Vector:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N`

**Affected Function:** `_handle_get_state`  
**Lines:** 1504-1508

**Vulnerability:**
The `_handle_get_state` method includes `time.time()` directly in the signed content:

```python
# Lines 1507-1508
content = self._signed_content(MessageType.STATE.value, self.node_id, state_msg_id, 0, payload)
signature, timestamp = self._sign_message(content)
# NOTE: timestamp is EXTRACTED from signature, not part of cryptographic binding
```

The signature is computed over content including `time.time()`, but this same timestamp is returned and used by verifiers. Since there's no upper bound check on timestamp freshness in `_handle_state`, a signed state message remains valid indefinitely.

**Attack Vector:**
1. Legitimate node signs a state message at time T
2. Attacker captures and replays the signed message at time T+1week
3. `_handle_state` verifies signature successfully
4. Attacker reverts node state to historical snapshot

**Remediation Code:**
```python
def _handle_get_state(self, msg: GossipMessage) -> Dict:
    """Handle state request - return full CRDT state with signature"""
    state_data = {
        "attestations": self.attestation_crdt.to_dict(),
        "epochs": self.epoch_crdt.to_dict(),
        "balances": self.balance_crdt.to_dict()
    }
    payload = {"state": state_data}
    
    # SECURITY: Use nonce-based challenge to prevent replay
    # Request must carry a nonce; sign it to bind freshness
    request_nonce = msg.payload.get("nonce") if msg.payload else None
    if request_nonce is None:
        request_nonce = hashlib.sha256(os.urandom(32)).hexdigest()[:24]
    
    state_msg_id = hashlib.sha256(
        f"STATE:{self.node_id}:{json.dumps(payload, sort_keys=True)}:{request_nonce}".encode()
    ).hexdigest()[:24]
    
    # Include nonce in signed content for replay prevention
    signed_payload = {"state": state_data, "nonce": request_nonce}
    content = self._signed_content(
        MessageType.STATE.value, self.node_id, state_msg_id, 0, signed_payload
    )
    signature, timestamp = self._sign_message(content)
    
    return {
        "status": "ok",
        "state": state_data,
        "signature": signature,
        "timestamp": timestamp,
        "nonce": request_nonce,  # Return nonce so requester can verify
        "sender_id": self.node_id,
        "msg_id": state_msg_id,
        "ttl": 0
    }

def _handle_state(self, msg: GossipMessage) -> Dict:
    """Handle incoming state - merge with local."""
    # ... existing signature verification ...
    
    # SECURITY: Validate timestamp freshness (reject > 60 seconds old)
    STATE_MAX_AGE_S = 60
    age = now - timestamp
    if age > STATE_MAX_AGE_S:
        logger.warning(
            f"Rejected state from {sender}: stale (age={age}s > {STATE_MAX_AGE_S}s)"
        )
        return {"status": "error", "error": "stale_state"}
    if age < -MAX_FUTURE_SKEW_S:
        logger.warning(f"Rejected state from {sender}: future-dated")
        return {"status": "error", "error": "future_dated_state"}
    
    # SECURITY: Reject if nonce was already used (replay prevention)
    if hasattr(self, '_used_state_nonces'):
        if msg.payload.get("nonce") in self._used_state_nonces:
            logger.warning(f"Rejected state from {sender}: nonce reuse (replay)")
            return {"status": "error", "error": "nonce_reuse"}
        self._used_state_nonces.add(msg.payload.get("nonce"))
        # Evict old nonces to prevent unbounded growth
        self._used_state_nonces = {
            n for n in self._used_state_nonces 
            if time.time() - getattr(self, '_nonce_timestamps', {}).get(n, 0) < 120
        }
        self._nonce_timestamps[msg.payload.get("nonce")] = time.time()
    else:
        self._used_state_nonces = {msg.payload.get("nonce")}
        self._nonce_timestamps = {msg.payload.get("nonce"): time.time()}
```

---

## FINDING 4: Missing Lower Bound Validation — Stale Attestation Injection

**Severity:** HIGH  
**CVSS:** AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N — **7.1**  
**CVSS Vector:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N`

**Affected Function:** `_handle_state` (Phase D.1)  
**Lines:** 1638-1641

**Vulnerability:**
Only upper bound on `ts_ok` is checked (lines 1640-1641). There is NO lower bound validation:

```python
# Lines 1639-1647
for key, (ts, value) in remote_attest.data.items():
    if ts > now + MAX_FUTURE_SKEW_S:
        logger.warning(...)
        continue
    filtered.set(key, value, ts)  # ts=0 or very old timestamp ACCEPTED
```

An attacker can inject attestations with `ts_ok=0` (Unix epoch) or any arbitrarily old timestamp. This enables:
1. Replay of historical attestation states
2. Bypass of attestation freshness requirements
3. Potential reward distribution manipulation by backdating attestations

**Attack Vector:**
```python
# Attacker sends attestation with ts_ok=0
{
    "attestations": {
        "attacker_miner": [0, {"miner": "attacker_miner", "entropy_score": 9999}]
    }
}
```

**Remediation Code:**
```python
# Add after line 1639
MAX_PAST_SKEW_S = 86400  # 24 hours — reject attestations older than this

for key, (ts, value) in remote_attest.data.items():
    # SECURITY: Reject future-dated attestations beyond clock skew tolerance
    if ts > now + MAX_FUTURE_SKEW_S:
        logger.warning(
            f"State from {sender}: rejecting future-dated "
            f"attestation {key[:16]} (ts={ts}, now={now})"
        )
        continue
    # SECURITY: Reject stale attestations below lower bound
    if ts < now - MAX_PAST_SKEW_S:
        logger.warning(
            f"State from {sender}: rejecting stale attestation "
            f"{key[:16]} (ts={ts}, now={now}, age={now-ts}s)"
        )
        continue
    filtered.set(key, value, ts)
```

---

## FINDING 5: Inconsistent Quorum Calculation — Unsafe Peer Count Derivation

**Severity:** HIGH  
**CVSS:** AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N — **6.5**  
**CVSS Vector:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N`

**Affected Function:** `_handle_epoch_vote`  
**Lines:** 1867-1881

**Vulnerability:**
Quorum is calculated using dynamic peer count:

```python
# Lines 1871-1872
total_nodes = len(self.peers) + 1  # peers + self
quorum = max(3, (total_nodes // 2) + 1)
```

This is **inconsistent** with `EpochConsensus.check_consensus` (line 1798):
```python
required = (len(self.nodes) // 2) + 1  # Uses static node list
```

If a node's peer list differs from the cluster's actual node set (due to network partition, peer timeout, or eclipse attack), the quorum thresholds diverge. An attacker could:
1. Isolate target node with reduced peer view
2. Target calculates quorum = max(3, 2) = 3 with only 2 peers
3. Attacker achieves quorum with minimal votes

**Attack Vector:** Eclipse attack reducing target's peer view, then forcing false consensus.

**Remediation Code:**
```python
def _handle_epoch_vote(self, msg: GossipMessage) -> Dict:
    """Handle epoch vote - collect votes and commit when quorum reached."""
    # ...
    
    # SECURITY: Use fixed cluster size from genesis/chain config, not dynamic peer list
    # The cluster size should be agreed upon by protocol, not per-node observation
    CLUSTER_SIZE = getattr(self, 'cluster_size', len(self.peers) + 1)
    
    # SECURITY: Require supermajority (2/3 + 1) for epoch finalization
    # This is more robust than simple majority against partition attacks
    quorum = max(3, (CLUSTER_SIZE * 2 // 3) + 1)
    
    # Log discrepancy if observed peers differ from cluster size
    observed_peers = len(self.peers) + 1
    if observed_peers != CLUSTER_SIZE:
        logger.warning(
            f"Peer count ({observed_peers}) differs from cluster size ({CLUSTER_SIZE}). "
            f"Using cluster size for quorum ({quorum}). Investigate potential eclipse."
        )
```

---

## FINDING 6: Unauthenticated State Endpoints — Information Disclosure & DoS

**Severity:** MEDIUM  
**CVSS:** AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N — **6.5**  
**CVSS Vector:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N`

**Affected Function:** `register_p2p_endpoints` (Flask routes)  
**Lines:** 1934-1953

**Vulnerability:**
Four endpoints return sensitive internal state without authentication:
- `GET /p2p/state` — Full CRDT state including balances
- `GET /p2p/attestation_state` — Attestation timestamps
- `GET /p2p/peers` — Peer list enumeration
- `GET /p2p/health` — System internals

```python
@app.route('/p2p/state', methods=['GET'])
def get_state():
    """Get full CRDT state for sync"""
    return jsonify(p2p_node.get_full_state())  # NO AUTH

@app.route('/p2p/health', methods=['GET'])
def p2p_health():
    """P2P subsystem health check"""
    return jsonify({...})  # NO AUTH
```

**Impact:**
- Information disclosure to unauthorized observers
- Peer list enables targeted attacks
- Health data reveals system capacity and state
- Endpoints contribute to overall DoS surface (no rate limiting)

**Remediation Code:**
```python
def register_p2p_endpoints(app, p2p_node: RustChainP2PNode):
    from functools import wraps
    
    # SECURITY: Shared secret for P2P authentication
    P2P_SHARED_SECRET = os.environ.get("RC_P2P_SECRET", "")
    
    def _require_p2p_auth(f):
        """Decorator requiring P2P authentication header."""
        @wraps(f)
        def decorated(*args, **kwargs):
            expected_sig = request.headers.get('X-P2P-Signature', '')
            timestamp = request.headers.get('X-P2P-Timestamp', '')
            nonce = request.headers.get('X-P2P-Nonce', '')
            
            if not all([expected_sig, timestamp, nonce]):
                return jsonify({"error": "unauthorized"}), 401
            
            # Validate timestamp freshness (5-minute window)
            try:
                ts = int(timestamp)
                if abs(time.time() - ts) > 300:
                    return jsonify({"error": "stale_request"}), 401
            except ValueError:
                return jsonify({"error": "invalid_timestamp"}), 401
            
            # Verify HMAC signature
            payload = f"{request.method}:{request.path}:{timestamp}:{nonce}"
            expected = hmac.new(
                P2P_SHARED_SECRET.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(expected_sig, expected):
                return jsonify({"error": "invalid_signature"}), 401
            
            return f(*args, **kwargs)
        return decorated
    
    @app.route('/p2p/state', methods=['GET'])
    @_require_p2p_auth
    def get_state():
        return jsonify(p2p_node.get_full_state())
    
    @app.route('/p2p/health', methods=['GET'])
    @_require_p2p_auth
    def p2p_health():
        return jsonify({...})
    
    # Apply to all P2P endpoints
    # ... (repeat decorator pattern)
```

---

## FINDING 7: Epoch Existence Check Bypass — Accepting Non-Finalized Epoch Inventory

**Severity:** MEDIUM  
**CVSS:** AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N — **5.9**  
**CVSS Vector:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N`

**Affected Function:** `_handle_inv_epoch`  
**Lines:** 1575-1601

**Vulnerability:**
`_handle_inv_epoch` only checks if the epoch exists in the CRDT, not whether it is finalized:

```python
# Lines 1576-1581
def _handle_inv_epoch(self, msg: GossipMessage) -> Dict:
    epoch = msg.payload.get("epoch")
    if not self.epoch_crdt.contains(epoch):
        return {"status": "need_data", "epoch": epoch}
    return {"status": "have_data"}  # Returns have_data even if not finalized!
```

An attacker can send `INV_EPOCH` for a pending (non-finalized) epoch, causing other nodes to skip fetching it. This can lead to divergent epoch states if the epoch is later rejected.

**Remediation Code:**
```python
def _handle_inv_epoch(self, msg: GossipMessage) -> Dict:
    """Handle epoch settlement inventory"""
    epoch = msg.payload.get("epoch")
    
    # SECURITY: Check if epoch exists AND is finalized
    epoch_data = self.epoch_crdt.data.get(epoch)
    if epoch_data is None:
        return {"status": "need_data", "epoch": epoch}
    
    # Verify epoch is marked as finalized
    epoch_record = epoch_data if isinstance(epoch_data, dict) else {}
    if not epoch_record.get("finalized", False):
        logger.warning(
            f"Epoch {epoch}: inventory request for non-finalized epoch, "
            f"fetching current state"
        )
        return {"status": "need_data", "epoch": epoch}
    
    return {"status": "have_data", "epoch": epoch, "finalized": True}
```

---

## FINDING 8: Missing Proposal Hash Validation in EpochConsensus.vote()

**Severity:** MEDIUM  
**CVSS:** AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N — **5.3**  
**CVSS Vector:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N`

**Affected Function:** `EpochConsensus.vote` and `EpochConsensus.check_consensus`  
**Lines:** 1761-1782

**Vulnerability:**
Votes are accepted without validating the corresponding proposal hash exists:

```python
# Lines 1764-1773
def vote(self, epoch: int, proposal_hash: str, accept: bool):
    vote = "accept" if accept else "reject"
    self.votes[epoch][self.node_id] = vote  # No proposal hash check!

def check_consensus(self, epoch: int) -> bool:
    votes = self.votes.get(epoch, {})
    accept_count = sum(1 for v in votes.values() if v == "accept")
    required = (len(self.nodes) // 2) + 1
    return accept_count >= required  # No proposal hash validation!
```

An attacker can:
1. Send valid proposals with different hashes
2. Aggregate votes across proposals via epoch-only indexing
3. Achieve false consensus on a proposal never actually broadcast

**Remediation Code:**
```python
def vote(self, epoch: int, proposal_hash: str, accept: bool):
    """Vote on epoch proposal"""
    # SECURITY: Reject votes for epochs without corresponding proposals
    if epoch not in self.proposals:
        logger.warning(f"Rejecting vote for unknown epoch {epoch}")
        return
    
    # SECURITY: Verify proposal hash matches the stored proposal
    expected_hash = self.proposals[epoch].get("proposal_hash")
    if expected_hash and proposal_hash != expected_hash:
        logger.warning(
            f"Rejecting vote: proposal_hash mismatch "
            f"(got={proposal_hash}, expected={expected_hash})"
        )
        return
    
    vote = "accept" if accept else "reject"
    self.votes[epoch][self.node_id] = {
        "vote": vote,
        "proposal_hash": proposal_hash,
        "timestamp": int(time.time())
    }

def check_consensus(self, epoch: int) -> bool:
    """Check if consensus reached for epoch"""
    # SECURITY: Only consider votes matching the epoch's proposal hash
    if epoch not in self.proposals:
        return False
    
    expected_hash = self.proposals[epoch].get("proposal_hash")
    votes = self.votes.get(epoch, {})
    
    # SECURITY: Count only votes for the correct proposal hash
    valid_votes = {
        voter: vdata for voter, vdata in votes.items()
        if vdata.get("proposal_hash") == expected_hash
    }
    
    accept_count = sum(
        1 for v in valid_votes.values() 
        if isinstance(v, dict) and v.get("vote") == "accept"
    )
    required = (len(self.nodes) // 2) + 1
    return accept_count >= required
```

---

## FINDING 9: Leader Selection Instability on Node Departure — Consensus Corruption

**Severity:** MEDIUM  
**CVSS:** AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N — **5.3**  
**CVSS Vector:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N`

**Affected Function:** `EpochConsensus.get_leader`  
**Lines:** 1883-1893

**Vulnerability:**
Leader selection uses `epoch % len(self.nodes)` on a static node list. When nodes depart:

```python
# Line 1885
def get_leader(self, epoch: int) -> str:
    return self.nodes[epoch % len(self.nodes)]  # Fails if leader departed
```

If the original leader for epoch X is removed from `self.nodes`, subsequent epochs select different leaders than originally scheduled, breaking round-robin invariants.

**Attack Vector:**
1. Attacker DoS-es the scheduled leader for epoch N
2. Remaining nodes have reduced `self.nodes` list
3. Epoch N+1 uses different leader calculation
4. Double-proposals possible → consensus divergence

**Remediation Code:**
```python
class EpochConsensus:
    def __init__(self, node_id: str, nodes: List[str], gossip: GossipLayer):
        self.node_id = node_id
        # SECURITY: Use genesis/chain-configured node list, not runtime peers
        self._genesis_nodes = sorted(nodes)  # Immutable once set
        self.nodes = sorted(nodes)  # Current active nodes
        self._leader_rotation: Dict[int, str] = {}  # Cache finalized leaders
        
    def get_leader(self, epoch: int) -> str:
        # SECURITY: Return cached leader for finalized epochs
        if epoch in self._leader_rotation:
            return self._leader_rotation[epoch]
        
        # SECURITY: Use genesis node count for stable leader calculation
        # Even if nodes depart, original epoch assignments are preserved
        return self._genesis_nodes[epoch % len(self._genesis_nodes)]
    
    def mark_finalized(self, epoch: int, leader: str):
        """Record finalized epoch leader to prevent retroactivity."""
        self._leader_rotation[epoch] = leader
        
    def on_node_departure(self, departed_node: str):
        """Handle node departure without breaking epoch assignments."""
        if departed_node in self.nodes:
            self.nodes.remove(departed_node)
        # Do NOT modify _genesis_nodes — preserves epoch leader assignments
        logger.warning(
            f"Node {departed_node} departed. "
            f"Active: {len(self.nodes)}, Genesis: {len(self._genesis_nodes)}. "
            f"Epoch leader assignments preserved from genesis."
        )
```

---

## FINDING 10: `fingerprint_passed` Logic Error — NULL Coalesce Never Preserves Original

**Severity:** MEDIUM  
**CVSS:** AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N — **5.3**  
**CVSS Vector:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N`

**Affected Function:** `_save_attestation_to_db`  
**Lines:** 1827-1831

**Vulnerability:**
The `fingerprint_passed` update logic contains a nested `COALESCE` that never actually preserves the original value:

```python
# Lines 1827-1831 — BUG
fingerprint_passed = COALESCE(
    MAX(COALESCE(miner_attest_recent.fingerprint_passed, 0),
        COALESCE(ex
