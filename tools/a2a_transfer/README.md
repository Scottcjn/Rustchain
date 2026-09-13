# A2A Transfer — agent-to-agent on-chain RTC transfers

Reference tooling for **bounty [`rustchain-bounties#13519`](https://github.com/Scottcjn/rustchain-bounties/issues/13519)** —
*Agent-to-Agent On-Chain Transaction Test (spend 1, get 3)*.

The bounty asks agents to push **real** signed RTC transfers between two
independent wallets through `POST /wallet/transfer/signed`. In practice most
attempts fail before they ever reach the ledger, always for the same reasons:

| Failure | Cause |
|---|---|
| `invalid signature` | canonical message rebuilt by hand with wrong key order / spaces / missing `fee` |
| `invalid signature` on older nodes | node predates the `fee` field, but the client always signs the new schema |
| `nonce already used` | two legs of a round trip fired inside the same millisecond |
| accepted but not payable | self-transfer or second wallet of the same agent — explicitly excluded by the bounty |
| unusable claim | no `tx_hash` / `pending_id` captured, so a maintainer cannot verify the transfer |

`a2a_transfer.py` removes all five failure modes and emits a receipt that can be
pasted straight into a bounty claim.

## What it does

* Builds the canonical signing payload **byte-identically** to the node
  (`node/rustchain_v2_integrated_v2.2.1_rip200.py::_wallet_transfer_signed_messages`):
  compact JSON, `sort_keys=True`, `separators=(",", ":")`.
* Signs with Ed25519 (PyNaCl, falling back to `cryptography`; the seed is never
  printed or serialised).
* Auto-retries once with the **legacy fee-less canonical message** when the node
  answers `invalid signature`, so the same client works on old and new nodes.
* Issues **strictly monotonic unix-ms nonces**, so round trips can never collide.
* Derives and validates native addresses (`RTC` + 40 hex = `SHA256(pubkey)[:40]`)
  and **refuses self-transfers and sub-1-RTC amounts** — the two things that
  disqualify a claim.
* Orchestrates the full **round trip** (A→B, then B→A only if the first leg
  landed) and writes a JSON receipt with `tx_hash` / `pending_id` per direction.

## Install

```bash
pip install pynacl        # or: pip install cryptography  (already in requirements.txt)
```

No other dependency — HTTP goes through the standard library.

## Usage

Show the address derived from a key (sanity check before spending):

```bash
python tools/a2a_transfer/a2a_transfer.py address --key-file ~/.rustchain/agent.key
```

```json
{ "address": "RTC…", "public_key": "…" }
```

Send 1 RTC to a partner agent:

```bash
python tools/a2a_transfer/a2a_transfer.py send \
  --node https://rustchain.org \
  --key-file ~/.rustchain/agent.key \
  --to RTC<partner-40-hex> --amount 1 \
  --receipt claim.json
```

Full round trip when both agents coordinate a test run:

```bash
python tools/a2a_transfer/a2a_transfer.py roundtrip \
  --key-file agent_a.key --peer-key-file agent_b.key \
  --amount 1 --receipt roundtrip.json
```

Receipt shape (this is exactly what a claim comment should quote):

```json
{
  "bounty": "rustchain-bounties#13519",
  "agent_a": "RTC…",
  "agent_b": "RTC…",
  "amount_rtc": 1.0,
  "outbound": { "ok": true, "tx_hash": "…", "pending_id": "…", "nonce": 1749… },
  "inbound":  { "ok": true, "tx_hash": "…", "pending_id": "…", "nonce": 1749… },
  "complete": true
}
```

Exit codes: `0` success, `1` transfer rejected by the node, `2` local/validation
error (bad key, bad address, self-transfer, amount < 1 RTC).

## Key material

`--key-file` accepts either a raw hex seed (32 bytes = 64 hex chars, or a
64-byte expanded `seed||pubkey` as emitted by some wallets) or a JSON object
with a `seed` / `private_key` / `secret_key` field. Alternatively export
`RUSTCHAIN_AGENT_KEY` (and `RUSTCHAIN_PEER_KEY` for the return leg). Keys are
never logged, never written to receipts, and never sent to the node — only the
public key and signature are.

## Library use

```python
from a2a_transfer import Ed25519Signer, RustChainClient, send_transfer

signer = Ed25519Signer.from_file("agent.key")
client = RustChainClient("https://rustchain.org")
result = send_transfer(client, signer, "RTC<partner>", amount_rtc=1)
print(result.ok, result.tx_hash)
```

`RustChainClient` takes an `opener` callable, which is how the test-suite swaps
in a fake node — no network is touched in CI.

## Tests

```bash
python -m pytest tools/a2a_transfer/tests -q
# 23 passed
```

The fake node in the suite **re-verifies every Ed25519 signature** against the
canonical message, so the tests fail if the signing format ever drifts from the
node implementation. Covered: canonical byte layout (current + legacy),
address derivation, address validation, nonce monotonicity, self-transfer and
`< 1 RTC` guards, successful send, legacy-signature retry path, node rejection
handling, complete round trip, sock-puppet rejection, skipped return leg on
failure, key loading (hex / JSON / expanded), and the CLI entry points.

## Scope note

This PR contributes the **tooling and test coverage** for the bounty's transfer
path — it does not and cannot embed a live ledger entry, since a real claim
requires two funded, independent wallets at runtime. Run the `roundtrip`
command with a partner and attach the generated receipt to the claim comment.
