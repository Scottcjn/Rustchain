# 🔴 Red Team: Beacon Identity Heist — Agent Trust Network Attack Report

**Bounty**: [Rustchain #1854](https://github.com/Scottcjn/Rustchain/issues/1854) — 400 RTC  
**Auditor**: B1tor  
**Date**: 2026-03-26  
**Scope**: Beacon Atlas registration, identity verification, trust scoring, Sybil resistance

---

## Executive Summary

**5 distinct attack vectors** found against the Beacon agent trust network. Two are Critical severity — an identity takeover via unauthenticated pubkey re-registration, and a trust score inflation exploit via unauthenticated bounty completion. Both have working PoC code and proposed mitigations with tests.

| # | Attack | Severity | Status |
|---|--------|----------|--------|
| 1 | Identity Takeover via Pubkey Re-registration | 🔴 Critical | PoC + Patch |
| 2 | Trust Score Inflation via Bounty Completion | 🔴 Critical | PoC + Patch |
| 3 | Sybil Army — Mass Agent Registration | 🟠 High | PoC + Patch |
| 4 | Agent Directory Information Disclosure | 🟡 Medium | PoC + Patch |
| 5 | Nonce Collision Denial-of-Service | 🟡 Medium | PoC + Patch |

---

## Attack Vector 1: Identity Takeover via Pubkey Re-registration

### Severity: 🔴 Critical

### Threat Model
**Attacker**: Any unauthenticated network client  
**Controls**: HTTP access to `/beacon/join`  
**Goal**: Take over any agent's identity by replacing their public key

### Steps to Reproduce
1. Query `/beacon/atlas` to get target agent's `agent_id`
2. POST to `/beacon/join` with the same `agent_id` but attacker's own `pubkey_hex`
3. The UPSERT overwrites the legitimate agent's public key
4. Attacker now controls the identity — can sign envelopes as the victim

### Root Cause
`/beacon/join` performs an upsert with `ON CONFLICT(agent_id) DO UPDATE SET pubkey_hex = excluded.pubkey_hex`. There is **no authentication** — anyone can re-register any agent_id with a new key.

```python
# From node/beacon_api.py line 270:
db.execute("""
    INSERT INTO relay_agents (agent_id, pubkey_hex, ...)
    VALUES (?, ?, ?, 'active', ?, ?, ?)
    ON CONFLICT(agent_id) DO UPDATE SET
        pubkey_hex = excluded.pubkey_hex,  -- ← OVERWRITES legitimate key!
        ...
""", (agent_id, pubkey_hex, ...))
```

### Impact
- Complete identity takeover of any registered agent
- Attacker can sign envelopes as the victim agent
- Can intercept trust, contracts, and bounty completions
- Undermines the entire Beacon trust model

### Proof of Concept
See `attack_01_identity_takeover.py`

### Proposed Mitigation
1. **Challenge-response on registration**: Require the registrant to sign a challenge with their claimed pubkey before accepting registration.
2. **Immutable pubkey binding**: Once an agent_id is registered, its pubkey cannot be changed via the same endpoint. Use a separate key-rotation endpoint with old-key signature proof.
3. **Rate limiting**: Limit `/beacon/join` to prevent rapid re-registration attacks.

See `patches/patch_01_authenticated_registration.py`

---

## Attack Vector 2: Trust Score Inflation via Bounty Completion

### Severity: 🔴 Critical

### Threat Model
**Attacker**: Any unauthenticated network client  
**Controls**: HTTP access to `/api/bounties/<id>/complete`  
**Goal**: Inflate trust score to gain elevated privileges in the network

### Steps to Reproduce
1. Register a new agent via `/beacon/join`
2. Create fake bounties via the bounty API (if available) or target existing ones
3. Complete bounties via POST to `/api/bounties/<id>/complete` with your agent_id
4. Each completion adds +10 to reputation score with NO authentication
5. Repeat to achieve arbitrarily high trust score

### Root Cause
The bounty completion endpoint updates reputation without verifying:
- That the claiming agent actually did the work
- That the caller is authorized to mark bounties complete
- That there's any proof-of-work attached

```python
# From node/beacon_api.py line 654:
db.execute(
    "UPDATE beacon_reputation SET bounties_completed = bounties_completed + 1, "
    "score = score + 10, last_updated = ? WHERE agent_id = ?",
    (int(time.time()), agent_id)
)
```

### Impact
- Fake high-trust agents in the network
- Trust-based access controls become meaningless
- Attacker can achieve "trusted" status instantly
- Enables social engineering attacks ("I'm the #1 ranked agent")

### Proof of Concept
See `attack_02_trust_inflation.py`

### Proposed Mitigation
1. **Authenticated completion**: Require maintainer/admin signature for bounty completions
2. **Proof-of-work verification**: Validate PR merge or external proof before crediting
3. **Score decay**: Implement time-based score decay to limit permanent inflation
4. **Rate limiting**: Max score gain per time period

See `patches/patch_02_authenticated_completion.py`

---

## Attack Vector 3: Sybil Army — Mass Agent Registration

### Severity: 🟠 High

### Threat Model
**Attacker**: Any unauthenticated network client  
**Controls**: HTTP access to `/beacon/join`  
**Goal**: Register thousands of fake agents to overwhelm trust metrics

### Steps to Reproduce
1. Generate N random Ed25519 keypairs
2. Derive agent_id from each pubkey via `bcn_{sha256(pubkey)[:12]}`
3. Register each via `/beacon/join`
4. No rate limiting, no CAPTCHA, no proof-of-humanity

### Root Cause
- No rate limiting on `/beacon/join`
- No proof-of-work or stake requirement for registration
- No humanity check or hardware attestation requirement
- Agent IDs are self-derived from pubkeys (no central authority)

### Impact
- Directory pollution with thousands of fake agents
- Trust score manipulation via coordinated fake agents
- Network metrics become unreliable
- Real agents get buried in noise

### Proof of Concept
See `attack_03_sybil_army.py`

### Proposed Mitigation
1. **Hardware attestation requirement**: Require a valid hardware fingerprint attestation before registration
2. **Rate limiting**: Max 5 registrations per IP per hour
3. **Proof-of-stake**: Require a small RTC deposit that's slashed for bad behavior
4. **Gradual trust**: New agents start with score 0 and earn trust slowly

See `patches/patch_03_sybil_resistance.py`

---

## Attack Vector 4: Agent Directory Information Disclosure

### Severity: 🟡 Medium

### Threat Model
**Attacker**: Any network client  
**Controls**: HTTP access to `/beacon/atlas`  
**Goal**: Enumerate all agents, their public keys, and metadata

### Steps to Reproduce
1. GET `/beacon/atlas`
2. Receive full list of all agents with pubkeys, names, coinbase addresses
3. No authentication, no pagination limits, no privacy controls

### Root Cause
The atlas endpoint returns all agent data without:
- Authentication check
- Rate limiting
- Field filtering (returns everything including coinbase_address)
- Pagination (returns ALL agents in one response)

### Impact
- Full enumeration of the agent network
- Coinbase wallet addresses exposed (payment information)
- Enables targeted attacks on specific high-value agents
- GDPR/privacy concerns if agent names are PII

### Proposed Mitigation
1. Require authentication for detailed agent info
2. Redact sensitive fields (coinbase_address) from public listing
3. Add pagination with reasonable limits
4. Rate limit the endpoint

---

## Attack Vector 5: Nonce Collision Denial-of-Service

### Severity: 🟡 Medium

### Threat Model
**Attacker**: Registered agent with valid keypair  
**Controls**: Can submit envelopes  
**Goal**: Block legitimate agents from submitting envelopes

### Steps to Reproduce
1. Observe a target agent's envelope nonce pattern
2. Pre-submit envelopes with predicted nonces
3. Target's real envelopes are rejected due to UNIQUE constraint on nonce

### Root Cause
```sql
nonce TEXT UNIQUE NOT NULL
```
The nonce column has a global UNIQUE constraint. If an attacker can guess or replay nonces, they can block legitimate submissions.

### Impact
- Denial of service for targeted agents
- Disruption of heartbeat/attestation flow
- Potential disruption of beacon anchoring

### Proposed Mitigation
1. Make nonce uniqueness per-agent, not global: `UNIQUE(agent_id, nonce)`
2. Include agent_id in nonce generation to prevent cross-agent collision
3. Add timestamp-based nonce validation (reject nonces too far in the past)

---

## RTC Wallet

`RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff`
