# RustChain Development Log

A chronological record of development milestones, infrastructure deployments,
and engineering decisions for the RustChain Proof-of-Antiquity blockchain.

---

## Oct 4, 2024 — Token Genesis
- Designed RTC tokenomics: 8,388,608 total supply (2^23)
- 6% premine for founder allocations
- Fair launch model, no ICO, no VC funding

## Oct 10, 2024 — Proof-of-Antiquity Concept
- Drafted PoA consensus: vintage hardware earns higher mining rewards
- PowerPC G4 = 2.5x, G5 = 2.0x, Apple Silicon = 1.2x
- Philosophy: every CPU has a voice

## Oct 20, 2024 — Sophiacord Bot Architecture
- Designed Sophia Elya AI personality for Discord
- Boris Volkov (Soviet commander) personality module
- MoE (Mixture of Experts) architecture for personality switching

## Nov 5, 2024 — Ergo Private Chain
- Deployed Ergo node with custom addressPrefix=32
- Internal mining enabled (PoA-style, minimal difficulty)
- Zero-fee transaction config for anchor operations

## Nov 15, 2024 — First PowerPC Miner
- Got rustchain_universal_miner.py running on PowerBook G4
- CPU detection via /proc/cpuinfo (7450/7447/7455 = G4)
- Python 2.3 compatibility layer for vintage Mac OS X

## Nov 25, 2024 — Halo CE Server
- Deployed Halo CE dedicated server at 192.168.0.121:2302
- SAPP mods for custom game modes
- Planned RTC reward integration for gaming achievements

## Dec 5, 2024 — Database Schema Design
- Designed core tables: balances, ledger, headers, epoch_state
- miner_attest_recent for attestation tracking
- epoch_rewards and epoch_enroll for settlement

## Dec 20, 2024 — VPS Infrastructure
- Provisioned LiquidWeb VPS at 50.28.86.131
- Deployed rustchain_v2_integrated.py as systemd service
- nginx reverse proxy with HTTPS (self-signed)

## Jan 8, 2025 — Multi-Miner Attestation
- Implemented /attest/submit endpoint
- Device family detection (PowerPC, ARM, x86_64)
- Attestation TTL: 24 hours (ATTESTATION_TTL = 86400)

## Jan 15, 2025 — Epoch Settlement
- 10-minute epochs with automatic settlement
- Time-aged multipliers: G4 2.5x decaying over 16.67 years
- 1 CPU = 1 Vote weighted by antiquity bonus

## Jan 22, 2025 — Vintage Mac Fleet Deployment
- PowerBook G4 miners at 192.168.0.115, 192.168.0.125
- Power Mac G5 Dual at 192.168.0.130
- Secure miner proxy for legacy TLS on old Macs

## Feb 3, 2025 — Halo CE Bridge
- GameSpy protocol monitoring for player events
- RTC rewards: 0.01 per kill, 0.05 per game win
- Discord announcements for game events

## Feb 10, 2025 — Wallet Cryptography
- BIP39 24-word mnemonic seed phrases
- Ed25519 elliptic curve digital signatures
- PBKDF2 key derivation (100,000 iterations)
- AES-256-GCM encrypted keystores

## Feb 18, 2025 — Block Explorer
- Uvicorn-based explorer at port 8092
- Transaction history, miner stats, epoch timeline
- nginx proxied at /explorer path

