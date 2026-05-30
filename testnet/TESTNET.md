# RustChain Testnet

A safe, disposable sandbox that runs the **same node code as mainnet** — same
consensus, same Ed25519 signing, same RIP-PoA hardware fingerprinting — but on
a **separate chain** (`rustchain-testnet-v2`) with its own genesis and a faucet.

> ⚠️ **Testnet coins have NO value.** They are not RTC. Do not buy, sell, or
> treat them as worth anything. The chain may be reset at any time.

## Why it exists

For contributors and AI-agent devs (you 👋) to:
- test a miner install without competing for real RTC,
- **validate security PRs** — consensus / wallet / bridge exploits and fixes —
  against a live node instead of poking mainnet,
- experiment with transfers, governance, and bounty flows using faucet RTC.

Because it mirrors mainnet rules, a fix that passes here behaves the same on
mainnet — but a mistake here costs nothing.

## Endpoints

| What | URL |
|------|-----|
| Node health | `https://sophiapower8-1.tailbac22e.ts.net/health` |
| Current epoch | `https://sophiapower8-1.tailbac22e.ts.net/epoch` |
| Miners | `https://sophiapower8-1.tailbac22e.ts.net/api/miners` |
| Faucet | `https://sophiapower8-1.tailbac22e.ts.net/faucet` |

**Live now** — public via Tailscale Funnel (auto-TLS), backed by the node on POWER8.

## Get test-RTC from the faucet

```bash
curl -X POST https://sophiapower8-1.tailbac22e.ts.net/faucet \
  -H "Content-Type: application/json" \
  -d '{"wallet": "RTC<your-address>"}'
```

Rate limit: **0.5 test-RTC per wallet/IP per 24h.**

## Point a miner at the testnet

Run the standard miner with the testnet node URL — everything else is identical
to mainnet (real fingerprint checks, real Ed25519 signing):

```bash
# Windows miner: edit RUSTCHAIN_API to the testnet host, or:
RUSTCHAIN_API=https://sophiapower8-1.tailbac22e.ts.net python rustchain_windows_miner.py
```

Your miner attests, enrolls, and earns **test**-RTC on the testnet chain. The
distinct `chain_id` means a testnet miner can never accidentally submit to
mainnet (or vice versa).

## Differences from mainnet

| | Mainnet | Testnet |
|--|---------|---------|
| chain_id | `rustchain-mainnet-v2` | `rustchain-testnet-v2` |
| coin value | real RTC | **none** (disposable) |
| genesis | Dec 2 2025 | per-deploy |
| reset | never | any time |
| faucet | no | yes |
| consensus / sigs / fingerprint | — | **identical** |

## For operators

Deployment is one idempotent script — see [`deploy_testnet.sh`](./deploy_testnet.sh).

```bash
# on the testnet host (POWER8):
cd ~/rustchain-testnet/Rustchain/testnet
./deploy_testnet.sh           # deploy / update
./deploy_testnet.sh --reset   # wipe + fresh genesis
```

Then expose it publicly with [`nginx/testnet.rustchain.conf`](./nginx/testnet.rustchain.conf)
on a host with a public IP.

### Host requirements (learned deploying on POWER8 S824, ppc64le)
- **Python ≥ 3.9** — the node uses PEP585 runtime generics (`tuple[str, ...]`)
  and `flask>=3.1`. The script auto-picks `python3.10`/`3.11`/`3.12`. POWER8's
  default `python3` is 3.8 (too old); a source-built `python3.10` lives at
  `/usr/local/bin/python3.10`.
- **SQLite** — if the chosen Python was built without the `_sqlite3` extension
  (common for source builds), the script installs `libsqlite3-dev` + `pysqlite3`
  and shims it in as the stdlib `sqlite3` module automatically.
- **`RC_P2P_SECRET`** — the node refuses to start without it; the script
  generates and persists one.

### Verified status
- ✅ **Live + public** at `https://sophiapower8-1.tailbac22e.ts.net` via Tailscale
  Funnel (auto-TLS). `chain_id=rustchain-testnet-v2`, fresh genesis, `/health` +
  `/epoch` return 200, chain advancing. Isolated from mainnet by distinct chain_id.
- ✅ **Persistent** — runs under systemd (`rustchain-testnet.service`,
  enabled + auto-restart) on POWER8 (Python 3.10 + pysqlite3 shim).
- ⚠️ **Rewards module**: a `_epoch_eligible_miners` import warning appears at
  boot (`rewards_implementation_rip200`); epoch settlement/rewards on testnet
  need a verification pass before miners can earn test-RTC.
- ⚠️ **Faucet** payout path (`faucet_service/`) still needs a live verification
  pass against the running node before announce.
