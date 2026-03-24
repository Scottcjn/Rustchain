# RustChain Architecture Overview – Draft v1

## Core Design

RustChain is a memory-preservation blockchain that uses entropy benchmarks, hardware age, and artifact rarity to validate and score block creation.

### Consensus: Proof of Antiquity (PoA)

Validators are scored based on:
- BIOS Timestamp (hardware age)
- Entropy runtime (SHA256 slow decryption)
- Physical device uniqueness (anti-VM, no spoofing)

Scores are packaged in `proof_of_antiquity.json`, signed, and submitted to the chain.

## Block Structure

Each block contains:
- 🔑 Validator ID (wallet from Ergo backend)
- 🕯️ BIOS timestamp + entropy duration
- 📜 NFT unlocks (badges)
- 📦 Optional attached lore metadata
- 🎖️ Score metadata (for leaderboard + faucet access)

## Token Emission

- 5 RUST / block → validator
- NFT badge may alter payout (e.g., “Paw Paw” adds retro bonus)
- Halving every 2 years or “epoch milestone”

## External Integration

- 🧰 ErgoTool CLI for wallet / tx signing
- 💠 Ergo NFT standards for soulbound badge issuance
- 🌉 Future EVM bridge (FlameBridge) for interoperability

## Network Goals

- ✅ Keep validator requirements low (Pentium III or older)
- ✅ Preserve retro OS compatibility
- ✅ Limit bloat via badge logs & off-chain metadata anchors
