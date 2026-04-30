# Self-Audit: node/rustchain_p2p_gossip.py

## Wallet
RTC4642c5ee8467f61ed91b5775b0eeba984dd776ba

## Module reviewed
- Path: node/rustchain_p2p_gossip.py
- Commit: 2bf16f232ae95d4b2b9bf948f9f53c2229ff965d
- Lines reviewed: whole-file (~1050 lines)

## Deliverable: 3 specific findings

### 1. TTL Included in Signed Content Breaks Multi-Hop Gossip Forwarding

- **Severity**: high
- **Location**: node/rustchain_p2p_gossip.py:199-202 (`_signed_content`), 467-470 (`handle_message` forwarding)
- **Description**: The `_signed_content()` static method includes `ttl` in the HMAC-signed payload: `f"{msg_type}:{sender_id}:{msg_id}:{ttl}:{json.dumps(payload, sort_keys=True)}"`. When a node receives a message and forwards it (lines 467-470), it decrements `msg.ttl -= 1` and re-broadcasts the *same message object* with the *original signature*. The receiving next-hop node calls `verify_message()`, which reconstructs the signed content with the new (decremented) TTL, producing a different HMAC. Verification fails silently, and the message is dropped. This means gossip propagation only works for direct-originator→single-hop delivery; all multi-hop relay is broken. While the `/p2p/state` full-sync endpoint partially compensates, the INV/GETDATA incremental sync model—which is the primary mechanism for real-time attestation and epoch propagation—is non-functional beyond 1 hop.
- **Reproduction**: Set up 3 nodes (A, B, C) where A peers with B, and B peers with C (but A does not peer with C). Node A broadcasts an `INV_ATTESTATION` with TTL=3. Node B receives it (TTL=3 matches signature), decrements to TTL=2, forwards to C. Node C calls `verify_message()` which reconstructs content with TTL=2, but the HMAC was computed with TTL=3. `hmac.compare_digest()` returns False. Message dropped. C never receives the attestation.
- **Recommendation**: Either (a) remove `ttl` from `_signed_content()` so it is not covered by the signature, or (b) re-sign the message at each hop with the decremented TTL (requires each forwarding node to have signing authority, which is already the case for HMAC mode).

### 2. Deduplication Before Signature Verification Enables Cache-Bypass DoS

- **Severity**: medium
- **Location**: node/rustchain_p2p_gossip.py:395-425 (`handle_message`)
- **Description**: In `handle_message()`, the deduplication check (`SELECT 1 FROM p2p_seen_messages WHERE msg_id = ?`) runs *before* signature verification. When a message has an invalid signature, it is rejected at line 414 but its `msg_id` is **never** recorded in the seen-messages set or database—only successfully verified messages reach the `INSERT OR IGNORE` at line 419. An attacker can therefore send the *same* message (same `msg_id`) with an invalid signature repeatedly. Each delivery bypasses the dedup cache, forces a full HMAC computation (`hmac.new + compare_digest`), and hits the database with a SELECT query. The dedup system provides zero protection against replayed-invalid-signature messages. With Python's GIL-bound HMAC at ~100k ops/sec on typical hardware, sustained flooding can exhaust CPU on the gossip handler thread.
- **Reproduction**: Craft a valid-looking `GossipMessage` JSON with a fixed `msg_id` and an invalid `signature` field. POST it to `/p2p/gossip` 10,000 times in a loop. Each request passes the dedup check (the msg_id is never recorded as "seen"), triggers `_verify_signature()` → HMAC computation, and returns `{"status": "invalid_signature"}`. Monitor CPU usage on the target node; observe no dedup protection kicking in.
- **Recommendation**: Record the `msg_id` as seen *before* signature verification (at the cost of accepting that invalid messages consume dedup slots). Alternatively, maintain a separate rate-limit table keyed by source IP or `sender_id` to cap verification attempts per sender per time window, independent of dedup state.

### 3. State Sync Responses Bypass Deduplication, Enabling Replay Within Expiry Window

- **Severity**: medium
- **Location**: node/rustchain_p2p_gossip.py:526-555 (`request_full_sync`), 634-645 (`/p2p/state` endpoint)
- **Description**: The `/p2p/state` endpoint returns raw CRDT state wrapped in a JSON dict (not a `GossipMessage`), signed with a one-off signature. The `request_full_sync()` method constructs a `GossipMessage` from the response and passes it to `_handle_state()`, which verifies the signature and merges the CRDT state. However, the constructed `GossipMessage` is never registered in the dedup system—the dedup check only runs inside `handle_message()`, not `_handle_state()`. An attacker who captures a legitimate state sync response (valid signature, valid timestamp within the 300-second `MESSAGE_EXPIRY` window) can replay it to the same node multiple times within that window. While LWW semantics prevent *downgrading* already-merged entries, (a) a freshly restarted node with empty CRDT state will accept the stale replay as truth, and (b) the repeated merge operations consume CPU and database writes unnecessarily. The 300-second window is large enough for meaningful replay.
- **Reproduction**: Set up a 2-node cluster. Node A calls `GET /p2p/state` from Node B and receives a signed state response. Capture this response (valid for 300 seconds). Before expiry, POST the captured response to Node A's `/p2p/gossip` endpoint 100 times as a `STATE`-type `GossipMessage`. Each time, `_handle_state()` verifies the (still-valid) signature and merges the state. If Node A restarted during the window, the stale state populates its CRDTs.
- **Recommendation**: (a) Register state-sync responses in the dedup system before merging (use the `msg_id` from the constructed `GossipMessage`). (b) Consider shortening `MESSAGE_EXPIRY` from 300s to 60s for state sync specifically. (c) Add a monotonic counter or epoch-bound nonce to state responses so each response is single-use.

## Known failures of this audit

- **No live network testing**: All analysis is static code review. The TTL forwarding bug (Finding 1) is deduced from code paths but was not confirmed on a running multi-node cluster. A 3-node integration test would be needed to confirm the exact failure mode (silent drop vs. exception vs. fallback).
- **Ed25519 path not exercised**: The `p2p_identity.py` module (imported at runtime) was not reviewed. The `SIGNING_MODE`, `LocalKeypair`, `PeerRegistry`, `pack_signature`, `unpack_signature`, and `verify_ed25519` functions could have additional vulnerabilities (e.g., signature malleability, key validation bypass) that compound the findings above. In "strict" mode, `_verify_signature()` always returns `False` for the non-`verify_message()` path (line 263), which may be intentional but is worth verifying.
- **Database concurrency not tested**: The module uses `sqlite3.connect()` (not a shared connection) with default isolation. Under high gossip load, concurrent writes to `p2p_seen_messages` from multiple Flask request threads could hit SQLite `SQLITE_BUSY` errors. The code catches generic `Exception` but the retry/degradation behavior was not analyzed.
- **No fuzzing of payload schema**: `_handle_attestation()` and `_handle_state()` do basic schema checks, but deeply nested or unexpectedly typed payload values (e.g., `payload` as a list instead of dict) were not tested for crash or unexpected behavior paths.
- **Rate limiting not present**: No per-IP or per-sender rate limiting exists on `/p2p/gossip`. This amplifies Finding 2 but was not analyzed as a standalone finding since it's a missing feature rather than a code bug.

## Confidence
- Overall confidence: 0.75
- Per-finding confidence: [0.85, 0.70, 0.65]
  - Finding 1 (TTL): High confidence — the signed-content construction and forwarding logic are clearly visible; the mismatch is deterministic. Confidence not 1.0 because I didn't test on a live cluster and there may be a re-signing path I missed.
  - Finding 2 (dedup bypass): Medium-high confidence — the control flow (dedup → verify → record) is unambiguous. The DoS impact depends on Python HMAC throughput which I estimated but didn't benchmark.
  - Finding 3 (state replay): Medium confidence — the bypass of dedup for state sync is clear from code, but the practical exploitability depends on network topology (attacker needs to be in the path or sniff traffic) and whether TLS prevents interception.

## What I would test next
1. **Multi-hop gossip integration test**: Deploy 3 nodes in a linear topology (A→B→C) and confirm that `INV_ATTESTATION`, `EPOCH_PROPOSE`, and other message types fail to propagate from A to C. Then apply the TTL fix and re-test.
2. **Dedup bypass DoS benchmark**: Write a load-test script that sends 100k messages with fixed `msg_id` and invalid signatures to `/p2p/gossip`, measuring request latency and CPU utilization to quantify the DoS impact of Finding 2.
3. **Ed25519 signing mode audit**: Review `p2p_identity.py` for key validation, signature malleability, and the "strict" mode enforcement path. The interaction between HMAC and Ed25519 dual-mode verification could have subtle bypass conditions.
4. **State sync replay under restart**: Kill a node, capture a state sync response from a peer, restart the node with empty state, and replay the captured response multiple times to verify Finding 3's impact on CRDT initialization.
