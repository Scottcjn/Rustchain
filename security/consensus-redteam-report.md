# RustChain Cross-Node Consensus Red Team Report

**Bounty:** #58 — Cross-Node Consensus Attacks (100–200 RTC)
**Researcher:** @B1tor
**RTC Wallet:** `RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff`
**Date:** 2026-03-28
**Scope:** `node/rustchain_bft_consensus.py`, `node/rustchain_p2p_gossip.py`, `node/rustchain_p2p_sync.py`, `node/consensus_probe.py`

---

## Executive Summary

A static code review of RustChain's PBFT consensus layer and P2P gossip subsystem reveals **two Critical**, **two High**, and **two Medium** severity vulnerabilities. The most severe issues stem from a hardcoded P2P signing secret and a single shared HMAC key across all nodes. Together, these flaws allow an unauthenticated attacker to forge arbitrary consensus messages, hijack consensus rounds, and achieve a complete Byzantine fault injection — breaking the 3-node BFT cluster with a single malicious actor.

All findings below are **static analysis only**. No production nodes were contacted.

---

## Findings

### [CRITICAL-1] Hardcoded P2P Signing Secret

**File:** `node/rustchain_p2p_gossip.py`
**CVSS (estimated):** 9.8 (AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H)

**Description:**

The P2P layer derives its HMAC signing key from an environment variable with a hardcoded default:

```python
P2P_SECRET = os.environ.get("RC_P2P_SECRET", "rustchain_p2p_secret_2025_decentralized")
```

This default value is committed to the public repository. Any attacker who reads the source code can compute valid HMAC-SHA256 signatures for **any gossip message** — including `PRE-PREPARE`, `PREPARE`, and `COMMIT` messages — without access to any node.

**Impact:** Full consensus message forgery. An attacker can inject fraudulent PBFT phases to manipulate which blocks are committed, cause honest nodes to accept invalid blocks, or drive the cluster into an inconsistent state.

**Proof of Concept:** See `security/consensus-poc/consensus_attack_poc.py` — the `demo_forged_preprepare()` and `demo_view_change_flood()` functions demonstrate forged message injection entirely locally.

**Remediation:**
- Remove all hardcoded default secrets.
- Rotate the secret immediately on all deployed nodes via environment variable injection.
- Enforce secret presence at startup: raise a fatal error if `RC_P2P_SECRET` is not set.
- Consider per-node asymmetric signing (see CRITICAL-2).

---

### [CRITICAL-2] Shared HMAC Key Across All Nodes

**File:** `node/rustchain_bft_consensus.py`
**CVSS (estimated):** 9.1 (AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H)

**Description:**

The BFT consensus module uses a single symmetric HMAC key shared by all nodes (noted in a comment: *"all nodes share key in testnet"*). Real PBFT security requires each node to have its own signing key so that messages can be attributed and verified per-sender.

With a shared secret:
- Compromising **any one** node exposes the signing key for **all** nodes.
- An attacker can forge messages that appear to originate from any node in the cluster, trivially reaching the `2f+1` threshold needed to commit a fraudulent value (with `f=1` in a 3-node cluster, only 2 matching `PREPARE` messages are needed).

**Impact:** Single-node compromise → full cluster compromise. Byzantine fault tolerance is entirely negated.

**Remediation:**
- Adopt asymmetric per-node signing: each node generates an Ed25519 or secp256k1 keypair; public keys are distributed out-of-band.
- PBFT messages should be signed with the sender's private key and verified with the sender's known public key.
- Remove the shared-secret pattern entirely.

---

### [HIGH-1] Message Replay Within 300-Second TTL Window

**File:** `node/rustchain_bft_consensus.py`, `node/rustchain_p2p_gossip.py`
**CVSS (estimated):** 7.5 (AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N)

**Description:**

Messages carry a timestamp and are accepted if within `MESSAGE_EXPIRY = 300` seconds of the current time. There is no nonce, sequence number, or message-ID deduplication cache. A valid `COMMIT` message observed in network traffic can be replayed verbatim up to 5 minutes later to re-trigger commitment of an already-processed block or to manipulate a new consensus round.

**Attack Scenario:**
1. Attacker passively observes P2P traffic (or uses the hardcoded secret to craft a fresh message).
2. Attacker captures a `COMMIT` message for block `N`.
3. During consensus for block `N+k`, the attacker replays the captured `COMMIT`, causing nodes to count it again toward the quorum threshold.

**Impact:** Replay-based consensus manipulation; potential double-commit or state corruption.

**Remediation:**
- Add a random nonce to every message; include it in the HMAC.
- Maintain a short-lived `seen_message_ids` set (keyed on `nonce + sender + sequence`) with TTL-based eviction.
- Alternatively, use monotonic sequence numbers per sender and reject out-of-order or previously-seen numbers.

---

### [HIGH-2] Hardcoded Admin Key Default

**File:** `node/rustchain_bft_consensus.py`, `node/rustchain_p2p_sync.py` (multiple files)
**CVSS (estimated):** 8.1 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N)

**Description:**

Admin API authentication falls back to a hardcoded default when the environment variable is absent:

```python
RC_ADMIN_KEY = os.environ.get("RC_ADMIN_KEY", "rustchain_admin_key_2025_secure64")
```

If any deployed node omits this environment variable (e.g., during initial setup or after a misconfiguration), the hardcoded key grants full administrative access — potentially including node configuration, peer management, and consensus parameter changes.

**Impact:** Unauthorized administrative access to any node that did not explicitly set `RC_ADMIN_KEY`.

**Remediation:**
- Eliminate the hardcoded fallback. Fail at startup if `RC_ADMIN_KEY` is not set.
- Rotate the key on all nodes immediately.
- Audit admin API endpoints for authorization checks and add rate limiting.

---

### [MEDIUM-1] TLS Verification Bypass Flag

**File:** `node/rustchain_p2p_gossip.py`, `node/rustchain_p2p_sync.py`
**CVSS (estimated):** 6.5 (AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:N)

**Description:**

TLS certificate verification is controlled by a runtime flag:

```python
TLS_VERIFY = os.environ.get("RUSTCHAIN_TLS_VERIFY", "true").lower() != "false"
```

If any node operator sets `RUSTCHAIN_TLS_VERIFY=false` (e.g., for local development and then forgets to revert it in production), all inter-node TLS connections become vulnerable to Man-in-the-Middle (MITM) attacks. An attacker on the same network path can intercept and modify P2P traffic without detection.

**Combined with CRITICAL-1:** TLS bypass + known HMAC secret = attacker can fully intercept, modify, and re-sign P2P messages in real time.

**Remediation:**
- Remove the `false` bypass entirely for production builds.
- If needed for testing, require an explicit compile-time or build flag rather than an environment variable.
- Pin TLS certificates (mutual TLS / certificate pinning) for inter-node communication.

---

### [MEDIUM-2] View Change DoS via Forged VIEW_CHANGE Flood

**File:** `node/rustchain_bft_consensus.py`
**CVSS (estimated):** 6.5 (AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H)

**Description:**

The consensus view-change timer is set to `VIEW_CHANGE_TIMEOUT = 90` seconds. When a node suspects the primary is faulty, it broadcasts a `VIEW_CHANGE` message and starts a new timer. With the hardcoded HMAC secret (CRITICAL-1), an attacker can forge valid `VIEW_CHANGE` messages for arbitrary views and node IDs, causing all honest nodes to continuously rotate the primary leader.

Since each forged `VIEW_CHANGE` resets the timer and triggers leader election logic, the cluster never stabilizes long enough to complete a consensus round. This is a Denial of Service against liveness — no blocks can be committed while the attack persists.

**Attack Rate:** An attacker only needs to inject one forged `VIEW_CHANGE` every ~90 seconds to maintain the DoS indefinitely.

**Impact:** Complete loss of consensus liveness; all transaction processing halts.

**Remediation:**
- Rate-limit `VIEW_CHANGE` messages per sender (requires per-node keys — see CRITICAL-2).
- Implement exponential backoff on view changes to limit thrashing.
- Require view-change messages to reference a valid checkpoint or evidence of primary failure.
- Only count `VIEW_CHANGE` messages from known validator set members.

---

## Attack Chain: Full Consensus Takeover

The six findings above combine into a complete attack chain:

```
1. Read P2P_SECRET from public source code  (CRITICAL-1)
   └─▶ Forge valid HMAC for any message type

2. Enumerate 3-node cluster topology via consensus_probe.py

3. Inject forged PRE-PREPARE for attacker-chosen block  (CRITICAL-1 + CRITICAL-2)
   └─▶ Attacker claims to be the primary node

4. Forge 2x PREPARE messages (from "node-2" and "node-3")  (CRITICAL-2)
   └─▶ Quorum reached (2f+1 = 2 of 3)

5. Forge 2x COMMIT messages  (CRITICAL-2)
   └─▶ Honest node commits attacker-chosen block

6. [Optional] Flood VIEW_CHANGE to prevent any recovery  (MEDIUM-2)

Result: Attacker controls committed block content. BFT provides zero protection.
```

---

## Recommendations Summary

| Priority | Action |
|----------|--------|
| Immediate | Rotate all secrets (`RC_P2P_SECRET`, `RC_ADMIN_KEY`) via env vars; restart nodes |
| Immediate | Fail-fast at startup if secrets are unset (no hardcoded defaults) |
| Short-term | Implement per-node Ed25519 keypairs; distribute public keys out-of-band |
| Short-term | Add message-ID nonces + deduplication cache to prevent replay |
| Short-term | Remove `RUSTCHAIN_TLS_VERIFY=false` bypass |
| Medium-term | Rate-limit and validate VIEW_CHANGE messages; require primary-failure evidence |
| Medium-term | Full BFT security audit before mainnet |

---

## Disclosure

This report was prepared as part of the RustChain bug bounty program (issue #58). All testing was performed against local code only. No production nodes were contacted or modified.

**Researcher:** @B1tor
**RTC Wallet:** `RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff`
