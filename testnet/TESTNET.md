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
| Node health | `https://<testnet-host>/health` |
| Current epoch | `https://<testnet-host>/epoch` |
| Miners | `https://<testnet-host>/api/miners` |
| Faucet | `https://<testnet-host>/faucet` |

(The operator will fill in `<testnet-host>` once the public proxy is live.)

## Get test-RTC from the faucet

```bash
curl -X POST https://<testnet-host>/faucet \
  -H "Content-Type: application/json" \
  -d '{"wallet": "RTC<your-address>"}'
```

Rate limit: **0.5 test-RTC per wallet/IP per 24h.**

## Point a miner at the testnet

Run the standard miner with the testnet node URL — everything else is identical
to mainnet (real fingerprint checks, real Ed25519 signing):

```bash
# Windows miner: edit RUSTCHAIN_API to the testnet host, or:
RUSTCHAIN_API=https://<testnet-host> python rustchain_windows_miner.py
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

**Status note:** the node + chain isolation are the verified core. The faucet
payout path (`faucet_service/`) still needs a live verification pass against the
running testnet node before it's announced — see the operator README.
