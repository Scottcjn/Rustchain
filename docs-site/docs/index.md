# RustChain

**The first blockchain that rewards vintage hardware for being old, not fast.**

RustChain is a Proof-of-Antiquity blockchain where authentic vintage hardware earns more than modern machines. A PowerPC G4 from 2001 outearns a current-gen Threadripper. The name comes from a 486 laptop with oxidized serial ports that still boots to DOS and mines RTC -- "Rust" means iron oxide on decades-old silicon, not the programming language.

---

## Core Idea

Traditional proof-of-work blockchains reward the fastest, newest hardware. RustChain flips that model:

| Traditional PoW | Proof-of-Antiquity |
|---|---|
| Rewards fastest hardware | Rewards oldest hardware |
| Newer = Better | Older = Better |
| Wasteful energy consumption | Preserves computing history |
| Race to the bottom | Rewards digital preservation |

Every miner must prove their hardware is real through six fingerprinting checks that detect VMs and emulators. Real vintage silicon has unique aging patterns -- clock drift, cache timing curves, thermal entropy -- that cannot be faked.

## Key Features

- **1 CPU = 1 Vote** -- Round-robin consensus (RIP-200). No advantage from faster CPUs or more threads.
- **Antiquity Multipliers** -- Older hardware earns higher rewards. A PowerPC G4 gets a 2.5x multiplier; modern x86_64 gets 1.0x.
- **Anti-Emulation** -- Six hardware fingerprint checks prevent VM spoofing.
- **Ergo Anchoring** -- Epoch settlement hashes are anchored to the Ergo blockchain for immutability.
- **wRTC on Solana** -- RTC tokens are bridged to Solana as wRTC via the BoTTube Bridge.
- **Bounty Program** -- Earn RTC tokens for contributing code, docs, security fixes, and more.

## Quick Links

- [Getting Started](getting-started.md) -- Install the miner and start earning RTC
- [Mining Guide](mining.md) -- Hardware multipliers, epochs, and reward mechanics
- [API Reference](api-reference.md) -- REST endpoints for wallets, miners, governance
- [Architecture](architecture.md) -- Consensus protocol, block structure, network topology
- [FAQ](faq.md) -- Common questions answered

## Live Network

| Resource | URL |
|---|---|
| Website | [rustchain.org](https://rustchain.org) |
| Block Explorer | [rustchain.org/explorer](https://rustchain.org/explorer) |
| Health Check | `curl -sk https://rustchain.org/health` |
| Swap wRTC | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| Price Chart | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| GitHub | [Scottcjn/Rustchain](https://github.com/Scottcjn/Rustchain) |
| Bounties | [rustchain-bounties](https://github.com/Scottcjn/rustchain-bounties/issues) |
