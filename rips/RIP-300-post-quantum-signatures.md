# RIP-300: Post-Quantum Signature Migration

| Field | Value |
|-------|-------|
| RIP | 300 |
| Title | Post-Quantum Signature Migration |
| Author | Scott Boudreaux (Elyan Labs) |
| Status | Draft |
| Created | 2026-04-01 |
| Requires | RIP-200 |

---

## Abstract

This proposal introduces a phased migration from Ed25519 to ML-DSA-44 (CRYSTALS-Dilithium2) post-quantum digital signatures for all RustChain wallet operations, attestation endpoints, and signed transfers. A hybrid scheme preserves backward compatibility during transition while binding existing classical keys to new post-quantum keys, ensuring that no wallet funds become vulnerable to quantum attack even if migration is incomplete at the time cryptographically relevant quantum computers arrive.

## Motivation

### The Quantum Threat to Ed25519

Google Quantum AI published results in March 2026 demonstrating that Ed25519 private keys can be recovered from public keys using fewer than 500,000 physical qubits in approximately 9 minutes of wall-clock computation. Current quantum hardware sits at roughly 1,100 qubits (IBM Condor), but roadmaps from IBM, Google, and PsiQuantum project 100K-1M physical qubit systems between 2029 and 2033.

RustChain currently relies exclusively on Ed25519 for:

- **Wallet keypairs** (`rustchain_crypto.py`) -- BIP39 seed to Ed25519 signing key
- **Signed transfers** (`/wallet/transfer/signed`) -- Ed25519 signature verification
- **Miner attestation** -- device identity binding via public key
- **Ergo anchor transactions** -- on-chain commitment signatures

Once a quantum adversary can derive Ed25519 private keys from on-chain public keys, every wallet with a published public key (which includes every wallet that has ever sent a signed transaction) is vulnerable to total fund extraction.

### Why Act Now

| Milestone | Estimated Date |
|-----------|---------------|
| Google 500K qubit paper | March 2026 (published) |
| RIP-300 Phase 1 (PQ-Ready) | Q3 2026 |
| IBM 100K qubit roadmap | 2029 |
| RIP-300 Phase 3 (PQ Enforcement) | Q1 2029 |
| Google/PsiQuantum 1M qubit target | 2031-2033 |

Cryptographic migrations in small networks are straightforward but require lead time for tooling, testing, wallet upgrades, and user education. Starting in 2026 gives RustChain a three-year runway before the realistic threat window opens.

### Precedent

- NIST finalized FIPS 204 (ML-DSA) in August 2024
- QANplatform deployed XLINK hybrid binding in production (2025)
- Signal Protocol migrated to PQXDH (X25519 + ML-KEM) in 2024
- Chrome TLS moved to ML-KEM-768 hybrid key exchange in 2024

RustChain should not be behind consumer messaging apps on post-quantum readiness.

## Specification

### 1. Algorithm Selection

**Primary post-quantum algorithm:** ML-DSA-44 (CRYSTALS-Dilithium2, NIST FIPS 204)

| Property | Ed25519 (current) | ML-DSA-44 (proposed) |
|----------|--------------------|----------------------|
| Public key size | 32 bytes | 1,312 bytes |
| Signature size | 64 bytes | 2,420 bytes |
| Secret key size | 64 bytes | 2,560 bytes |
| Sign time | ~0.01ms | ~0.05ms |
| Verify time | ~0.01ms | ~0.028ms |
| Security level | 128-bit classical | NIST Level 2 (~128-bit post-quantum) |
| Assumption | ECDLP hardness | Module-LWE + SelfTargetMSIS |
| NIST standard | -- | FIPS 204 (Aug 2024) |

**Rationale for ML-DSA-44 over alternatives:**

- **ML-DSA-87 (Dilithium5):** NIST Level 5 is overkill for RustChain's threat model. 4,627-byte signatures increase storage and network cost for marginal benefit.
- **FALCON-512:** Faster verification but requires constant-time floating point, complicating portable implementations on vintage hardware (G4/G5 FPUs vary).
- **SPHINCS+-128f:** Hash-based, conservative assumptions, but 17KB signatures are prohibitive.
- **SLH-DSA (SPHINCS+):** Stateless hash-based, excellent fallback if lattice assumptions break, but signature size (~7-8KB at Level 1) is 3x ML-DSA-44.

ML-DSA-44 provides the best balance of security, signature size, verification speed, and library maturity.

### 2. Hybrid Signature Scheme

All signatures during the transition period (Phase 2) use a **concatenated hybrid** scheme:

```
HybridSignature = Ed25519_Sign(msg) || ML-DSA-44_Sign(msg)
                  [64 bytes]           [2,420 bytes]
                  Total: 2,484 bytes

HybridPubKey = Ed25519_PubKey || ML-DSA-44_PubKey
               [32 bytes]        [1,312 bytes]
               Total: 1,344 bytes
```

**Verification rule (Phase 2):** Both signatures MUST verify independently against the same message. If either fails, the transaction is rejected. This ensures security even if one algorithm is broken.

**Verification rule (Phase 3):** Only ML-DSA-44 signature is required. Ed25519 component may be omitted (set to 64 zero bytes).

### 3. Key Binding (XLINK Model)

Inspired by QANplatform's XLINK mechanism, existing Ed25519 wallets bind to a new ML-DSA-44 keypair via a **binding transaction**:

```json
{
  "type": "pq_key_bind",
  "ed25519_pubkey": "<existing 32-byte hex pubkey>",
  "mldsa44_pubkey": "<new 1312-byte hex pubkey>",
  "nonce": 1711929600000,
  "ed25519_signature": "<signs the mldsa44_pubkey + nonce>",
  "mldsa44_signature": "<signs the ed25519_pubkey + nonce>"
}
```

Both keys sign the other's public key, creating a cryptographic cross-binding that proves possession of both private keys at binding time. Once bound, the server records the association and requires hybrid signatures for all subsequent operations from that wallet.

**Binding is one-way and permanent.** A bound wallet cannot unbind or replace its PQ key. If the PQ key is compromised, the wallet must migrate funds to a new RTCQ address.

### 4. Address Format

Post-quantum-enabled wallets use the `RTCQ` prefix:

```python
# Current Ed25519 address
address = "RTC" + sha256(ed25519_pubkey)[:40]
# Example: RTCa1b2c3d4e5f6789012345678901234567890ab

# New PQ-enabled address
address = "RTCQ" + sha256(ed25519_pubkey || mldsa44_pubkey)[:40]
# Example: RTCQa1b2c3d4e5f6789012345678901234567890ab
```

Total address length is 44 characters. The `RTCQ` prefix signals to wallets and explorers that this address requires post-quantum signature verification.

**Address derivation is deterministic:** Given the same Ed25519 and ML-DSA-44 keypair, the RTCQ address is always the same.

### 5. Keystore v2

The encrypted keystore format is extended to hold both keypairs:

```json
{
  "version": 2,
  "address": "RTCQa1b2c3d4...",
  "legacy_address": "RTCa1b2c3d4...",
  "ed_public_key": "<32-byte hex>",
  "pq_public_key": "<1312-byte hex>",
  "salt": "<base64>",
  "nonce": "<base64>",
  "ciphertext": "<base64, encrypts ed_private_key + pq_public_key + pq_secret_key + mnemonic>",
  "kdf": "PBKDF2-SHA256",
  "kdf_iterations": 100000,
  "cipher": "AES-256-GCM",
  "created": "2026-04-01T00:00:00Z",
  "signature_scheme": "hybrid-ed25519-mldsa44"
}
```

The encrypted payload contains the private keys plus the mnemonic. Until the backend exposes seeded ML-DSA key generation, the keystore is the authoritative backup for the PQ component.

**Keystore v1 files continue to work** with Ed25519-only wallets until Phase 3 enforcement.

### 6. BIP39 Seed Derivation

The Phase 1 implementation derives **seed material** for ML-DSA-44 from the same BIP39 24-word mnemonic using a distinct derivation path:

```python
# Ed25519 (existing)
seed = Mnemonic.to_seed(mnemonic, passphrase)
ed25519_seed = sha256(seed).digest()
ed25519_keypair = Ed25519.from_seed(ed25519_seed)

# ML-DSA-44 (future seeded backend)
pq_seed_material = HMAC_SHA512(PQ_SEED_SALT, seed)
mldsa44_keypair = ML_DSA_44.keygen(seed=pq_seed_material)  # not available in pqcrypto today
```

Using distinct PQ seed material keeps the design ready for deterministic restore once the backend supports seeded ML-DSA key generation. In the current Phase 1 implementation, users must back up the encrypted keystore to preserve the PQ keypair.

### 7. Transaction Format

**Phase 1 (PQ-Ready):** No change to transaction format. Wallets generate PQ keys internally but do not use them on-chain.

**Phase 2 (Hybrid Signing):**

```json
{
  "from_address": "RTCQa1b2c3d4...",
  "to_address": "RTCQe5f6a7b8...",
  "amount_rtc": 50.0,
  "memo": "Payment",
  "nonce": 1711929600000,
  "signature_scheme": "hybrid-ed25519-mldsa44",
  "signature": "<64-byte hex Ed25519 signature>",
  "pq_signature": "<2420-byte hex ML-DSA-44 signature>",
  "public_key": "<32-byte hex Ed25519 public key>",
  "pq_public_key": "<1312-byte hex ML-DSA-44 public key>"
}
```

The `signature_scheme` field is new. Transactions without this field default to `"ed25519"` for backward compatibility.

**Phase 3 (PQ Enforcement):**

```json
{
  "from_address": "RTCQa1b2c3d4...",
  "to_address": "RTCQe5f6a7b8...",
  "amount_rtc": 50.0,
  "memo": "Payment",
  "nonce": 1711929600000,
  "signature_scheme": "mldsa44",
  "pq_signature": "<2420-byte hex>",
  "pq_public_key": "<1312-byte hex>"
}
```

Ed25519-only transactions (from `RTC`-prefix addresses without PQ binding) are rejected after the Phase 3 cutoff block.

### 8. Server Verification Logic

```python
def verify_transaction(tx: dict) -> tuple[bool, str]:
    scheme = tx.get("signature_scheme", "ed25519")

    if scheme == "ed25519":
        if phase >= 3 and not is_before_cutoff(tx):
            return False, "ed25519_rejected_post_cutoff"
        return verify_ed25519(tx["public_key"], tx["signature"], tx_message(tx))

    elif scheme == "hybrid-ed25519-mldsa44":
        ed_pub = tx["public_key"]            # 32 bytes hex
        pq_pub = tx["pq_public_key"]         # 1312 bytes hex
        ed_sig = tx["signature"]             # 64 bytes hex
        pq_sig = tx["pq_signature"]          # 2420 bytes hex
        msg = tx_message(tx)

        ed_ok = verify_ed25519(ed_pub, ed_sig, msg)
        pq_ok = verify_mldsa44(pq_pub, msg, pq_sig) is True

        if not ed_ok:
            return False, "ed25519_signature_invalid"
        if not pq_ok:
            return False, "mldsa44_signature_invalid"

        # Verify pubkey matches address
        expected_addr = "RTCQ" + sha256(bytes.fromhex(ed_pub) + bytes.fromhex(pq_pub)).hexdigest()[:40]
        if tx["from_address"] != expected_addr:
            return False, "address_pubkey_mismatch"

        return True, "valid_hybrid"

    elif scheme == "mldsa44":
        if phase < 3:
            return False, "pq_only_not_yet_accepted"
        return verify_mldsa44(tx["pq_public_key"], tx_message(tx), tx["pq_signature"])

    return False, "unknown_signature_scheme"
```

### 9. Attestation Endpoint Changes

The `/attest/submit` endpoint accepts an optional `pq_pubkey` field in the attestation payload:

```json
{
  "miner": "miner-wallet-id",
  "miner_id": "unique-miner-id",
  "nonce": "...",
  "pq_pubkey": "<1312-byte hex ML-DSA-44 public key>",
  "report": { "..." },
  "device": { "..." },
  "fingerprint": { "..." }
}
```

When present, the server stores the PQ public key in `miner_attest_recent` (new column `pq_pubkey TEXT`). During Phase 3, attestation submissions without a valid PQ public key are rejected.

### 10. Python Implementation

The `pqcrypto` package provides ML-DSA-44 bindings:

```python
from pqcrypto.sign.ml_dsa_44 import generate_keypair, sign, verify

# Key generation
public_key, secret_key = generate_keypair()

# Signing
signature = sign(secret_key, message)

# Verification
valid = verify(public_key, message, signature)
```

**Fallback:** If `pqcrypto` is unavailable (vintage systems), the `oqs` package (liboqs Python wrapper) provides equivalent functionality:

```python
import oqs
signer = oqs.Signature("Dilithium2")
public_key = signer.generate_keypair()
signature = signer.sign(message)
verifier = oqs.Signature("Dilithium2")
valid = verifier.verify(message, signature, public_key)
```

## Migration Path

### Phase 1: PQ-Ready (Q3 2026)

**Goal:** All wallet software can generate and store ML-DSA-44 keypairs. No on-chain changes. Zero breaking changes.

**Deliverables:**

1. `rustchain_crypto.py` extended with `RustChainPQWallet` class
2. Keystore v2 format with dual keypair storage
3. PQ seed-material derivation for ML-DSA-44 (`PQ_SEED_SALT`) and a future seeded-backend hook
4. `RTCQ` address generation
5. All 4 wallet GUIs updated:
   - `rustchain_wallet_gui.py`
   - `rustchain_wallet_founder.py`
   - `rustchain_wallet_secure.py`
   - `rustchain_wallet_founder_secure.py`
6. `pqcrypto` added to wallet build dependencies
7. Key binding transaction type defined (not yet enforced)
8. Wallet migration tool: generate PQ keypair from existing seed phrase and persist it in keystore v2

**Acceptance criteria:** A user can create a new wallet with an RTCQ address, export/import keystore v2, and restore the same RTCQ address from the keystore. Mnemonic-only deterministic RTCQ restore remains deferred until a seeded ML-DSA backend is adopted. No server changes required.

### Phase 2: Hybrid Signing (Q1 2027)

**Goal:** Transactions can carry hybrid signatures. Server verifies both. Ed25519-only transactions remain valid.

**Deliverables:**

1. Server updated to accept `signature_scheme: "hybrid-ed25519-mldsa44"`
2. `/wallet/transfer/signed` endpoint handles hybrid verification
3. Key binding endpoint (`/wallet/bind-pq`) deployed
4. Block explorer shows PQ binding status per wallet
5. Miner attestation accepts `pq_pubkey` field
6. `miner_attest_recent` schema updated with `pq_pubkey` column
7. Node-to-node sync includes PQ binding records
8. All 4 attestation nodes updated (Nodes 1-4)
9. Documentation and migration guide published
10. Wallet GUIs prompt users to bind PQ keys on startup

**Acceptance criteria:** A wallet can submit a hybrid-signed transaction that is accepted by all 4 nodes. Existing Ed25519-only wallets continue to function without changes.

### Phase 3: PQ Enforcement (Q1 2029)

**Goal:** Ed25519-only signatures are rejected after the cutoff block. All active wallets must have PQ binding.

**Deliverables:**

1. Cutoff block height announced 6 months in advance
2. Server rejects Ed25519-only transactions after cutoff
3. Attestation requires `pq_pubkey` field
4. Grace period: 90 days of warning logs before hard rejection
5. Abandoned wallet protection (see Security Considerations)
6. Post-cutoff, `mldsa44`-only signatures accepted (Ed25519 component optional)

**Acceptance criteria:** After the cutoff block, only hybrid or PQ-only transactions are accepted. Ed25519-only transactions return HTTP 400 with clear error message directing users to upgrade.

**Trigger condition:** Phase 3 activates at a specific block height OR if credible reports indicate quantum hardware capable of breaking Ed25519 exists, whichever comes first.

## Backwards Compatibility

### Existing Wallets (RTC-prefix)

- **Phase 1-2:** Continue to work exactly as today. No forced migration.
- **Phase 2 onward:** Wallets are prompted (not required) to bind a PQ key.
- **Phase 3:** Must bind PQ key or funds cannot be spent. Users who have lost their seed phrase can still receive funds to their RTC address but cannot send.

### Existing Keystore v1 Files

- Keystore v1 files are read by all wallet software indefinitely.
- On first unlock after Phase 1 deployment, the wallet offers to upgrade to v2 format.
- Upgrade is optional until Phase 3.

### Miner Attestation

- Miners without PQ public keys continue to attest and earn rewards through Phase 2.
- Phase 3 requires PQ public key in attestation payload.
- Vintage miners (G4/G5) that cannot run `pqcrypto` natively use the Sophia NAS proxy (see below).

### Ergo Anchor

The Ergo anchor system (`ergo_miner_anchor.py`, `rustchain_ergo_anchor.py`) depends on Ergo's own cryptographic primitives. Post-quantum migration for Ergo anchoring is **out of scope** for RIP-300 and will be addressed separately if/when the Ergo project adopts PQ signatures.

### Vintage Miner Support

PowerPC G4 and G5 miners cannot run modern Python packages natively. The existing `miner_proxy_secure.py` on Sophia NAS (192.168.0.160) is extended to provide **PQ signing as a service**:

1. Vintage miner submits attestation to proxy over LAN (HTTP, no TLS required on trusted LAN).
2. Proxy holds the miner's PQ private key (encrypted at rest, unlocked on proxy startup).
3. Proxy signs the attestation with both Ed25519 (miner's own) and ML-DSA-44 (proxy-held).
4. Proxy forwards the hybrid-signed attestation to the node.

This is acceptable because:
- The proxy already handles TLS termination for vintage clients.
- The LAN is trusted (same physical network, IP-whitelisted).
- The PQ key only protects against quantum attack; classical Ed25519 is still miner-held.
- If the proxy is compromised, the attacker gains the PQ key but still needs the Ed25519 key (held only on the vintage hardware) to forge a hybrid signature.

## Security Considerations

### Why Hybrid, Not Direct Replacement

A hybrid scheme protects against two failure modes:

1. **ML-DSA-44 is broken classically:** Ed25519 still protects the wallet.
2. **Ed25519 is broken quantumly:** ML-DSA-44 still protects the wallet.

Neither algorithm alone covers both cases. The hybrid scheme is secure as long as at least one algorithm remains unbroken.

### Why ML-DSA-44, Not ML-DSA-65 or ML-DSA-87

NIST Level 2 (ML-DSA-44) provides approximately 128-bit post-quantum security. RustChain's threat model does not require Level 5 (256-bit PQ). The smaller key and signature sizes reduce storage and bandwidth costs, which matters for miner attestation traffic across 4+ nodes.

If lattice-based cryptography is fundamentally broken (not just weakened), the correct response is migration to hash-based signatures (SLH-DSA), not a larger lattice parameter. A future RIP may address this scenario.

### Abandoned Wallets

Wallets that hold RTC but whose owners have lost access (lost seed phrase, deceased, etc.) cannot bind a PQ key. After Phase 3:

- **Funds remain on-chain** and visible in the block explorer.
- **Funds cannot be moved** (no valid signature possible).
- **Funds are NOT burned** -- they remain in `balances` table.
- **Recovery:** Until a seeded ML-DSA backend exists, recovery requires the Phase 1 encrypted keystore (or another preserved copy of the PQ secret key). Mnemonic-only recovery of the PQ component is deferred.

A quantum attacker who extracts the Ed25519 private key from an abandoned wallet's public key still cannot spend the funds because post-Phase-3 transactions require a PQ signature, and the PQ private key was never published on-chain.

### Public Key Exposure Minimization

Best practice: Wallets SHOULD use fresh RTCQ addresses for receiving. The PQ public key is only revealed when a transaction is sent (just as Ed25519 public keys are today). This limits the window for quantum precomputation.

### Side-Channel Resistance

ML-DSA-44 implementations MUST use constant-time operations. The `pqcrypto` package uses the NIST reference C implementation compiled with constant-time flags. The `oqs` package uses liboqs, which undergoes regular side-channel review.

On vintage hardware (G4/G5) where constant-time guarantees are harder to verify, PQ operations are delegated to the proxy server running on modern hardware (Sophia NAS, x86_64).

### Quantum-Safe RNG

ML-DSA-44 key generation requires a cryptographically secure random number generator. On Linux systems, `/dev/urandom` (backed by the kernel CSPRNG) is acceptable. On vintage Macs, the proxy server generates PQ keys using the modern host's RNG.

## Storage and Network Impact

At RustChain's current scale (dozens of miners, hundreds of transactions per day), the increased signature and key sizes are negligible:

| Data | Ed25519 | Hybrid | Increase |
|------|---------|--------|----------|
| Transaction signature | 64 B | 2,484 B | ~38x |
| Public key per TX | 32 B | 1,344 B | ~42x |
| Keystore file | ~500 B | ~8,000 B | ~16x |
| Attestation record | ~200 B | ~2,800 B | ~14x |

For context: 1,000 hybrid transactions per day would add approximately 3.8 MB of signature data. The SQLite database can handle this without schema or performance concerns.

At scale (thousands of miners), the increased data volume may motivate signature aggregation or compression schemes, addressable in a future RIP.

## Files Affected

| File | Change |
|------|--------|
| `rustchain_crypto.py` | Add `RustChainPQWallet` class, hybrid signing, keystore v2 |
| `rustchain_v2_integrated_v2.2.1_rip200.py` | Hybrid verification in `/wallet/transfer/signed`, key binding endpoint, attestation PQ field |
| `rustchain_wallet_gui.py` | RTCQ address display, PQ key generation UI |
| `rustchain_wallet_founder.py` | Same as above |
| `rustchain_wallet_secure.py` | Same as above |
| `rustchain_wallet_founder_secure.py` | Same as above |
| `miner_proxy_secure.py` | PQ signing proxy for vintage miners |
| `fingerprint_checks.py` | No change (fingerprint is orthogonal to signature scheme) |
| `ergo_miner_anchor.py` | No change (out of scope, see Backwards Compatibility) |
| `rip_200_round_robin_1cpu1vote.py` | No change (reward calculation unaffected) |

## Reference Implementation

Reference implementation will be provided as a pull request to `Scottcjn/rustchain` upon RIP-300 acceptance. The PR will include:

1. `rustchain_crypto.py` with `RustChainPQWallet` class (Phase 1)
2. Keystore v2 read/write (Phase 1)
3. Unit tests for key derivation, hybrid signing, and verification
4. Migration tool for existing wallets
5. Updated build script with `pqcrypto` dependency

## References

1. **Google Quantum AI (March 2026).** "Efficient Quantum Algorithms for Elliptic Curve Discrete Logarithms." Demonstrates Ed25519 key recovery with <500K physical qubits.

2. **NIST FIPS 204 (August 2024).** "Module-Lattice-Based Digital Signature Standard (ML-DSA)." https://csrc.nist.gov/pubs/fips/204/final

3. **NIST FIPS 203 (August 2024).** "Module-Lattice-Based Key-Encapsulation Mechanism Standard (ML-KEM)." https://csrc.nist.gov/pubs/fips/203/final

4. **QANplatform XLINK.** Hybrid classical-quantum key binding mechanism for blockchain wallets. https://www.qanplatform.com/

5. **Signal PQXDH (September 2023).** Post-quantum Extended Diffie-Hellman for Signal Protocol. https://signal.org/docs/specifications/pqxdh/

6. **RIP-200: Round-Robin 1-CPU-1-Vote Attestation.** Existing RustChain consensus and attestation framework that RIP-300 builds upon.

7. **CRYSTALS-Dilithium (Ducas et al., 2018).** "CRYSTALS-Dilithium: A Lattice-Based Digital Signature Scheme." https://pq-crystals.org/dilithium/

8. **IBM Quantum Roadmap (2025).** 100,000-qubit systems targeted for 2029. https://www.ibm.com/quantum/roadmap

9. **Bernstein, D.J. & Lange, T. (2017).** "Post-quantum cryptography." Nature 549, 188-194. Overview of post-quantum algorithm families.

10. **RustChain Wallet Security System (RIP-300 Appendix A).** Existing Ed25519 wallet implementation in `rustchain_crypto.py`.

---

## Appendix A: Test Vectors

To be provided with the reference implementation. Will include:

- Known-answer tests (KAT) for ML-DSA-44 seed-material derivation and keystore-backed restore
- Hybrid signature generation and verification test cases
- RTCQ address derivation test vectors
- Keystore v2 encryption/decryption round-trip tests
- Key binding transaction serialization and verification

## Appendix B: Upgrade Checklist for Node Operators

1. Install `pqcrypto` Python package: `pip install pqcrypto`
2. Update `rustchain_v2_integrated_v2.2.1_rip200.py` to version with RIP-300 support
3. Run database migration: `ALTER TABLE miner_attest_recent ADD COLUMN pq_pubkey TEXT;`
4. Restart node service: `systemctl restart rustchain`
5. Verify hybrid verification works: `curl -X POST /wallet/transfer/signed` with test hybrid TX
6. (Phase 3 only) Set `PQ_ENFORCEMENT=1` environment variable after cutoff block

## Appendix C: Timeline Summary

```
2026 Q3  Phase 1: PQ-Ready
         - Wallet software generates ML-DSA-44 keys
         - Keystore v2 format
         - RTCQ addresses
         - No server changes required

2027 Q1  Phase 2: Hybrid Signing
         - Server accepts hybrid signatures
         - Key binding endpoint live
         - Miners can submit PQ public keys
         - Ed25519-only still accepted

2028 Q3  Phase 3 Announcement
         - Cutoff block height announced
         - 6-month migration window begins
         - Wallet GUIs show prominent migration warnings

2029 Q1  Phase 3: PQ Enforcement
         - Ed25519-only transactions rejected
         - Attestation requires PQ public key
         - Hybrid or PQ-only signatures required
```
