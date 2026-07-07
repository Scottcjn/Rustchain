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

- 1.5 RTC per epoch to validators (fixed, no halving)
- Epoch = 144 blocks (~24 hours); pool split by antiquity weight
- NFT badge may alter an individual payout (e.g., "Paw Paw" adds a retro bonus)
- Fixed emission until the 8,388,608 RTC (2^23) cap, per RIP-0004

## External Integration

- 🧰 ErgoTool CLI for wallet / tx signing
- 💠 Ergo NFT standards for soulbound badge issuance
- 🌉 Future EVM bridge (FlameBridge) for interoperability

## Network Goals

- ✅ Keep validator requirements low (Pentium III or older)
- ✅ Preserve retro OS compatibility
- ✅ Limit bloat via badge logs & off-chain metadata anchors
