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

## Feb 28, 2025 — Wallet GUI Editions
- Standard wallet for end users
- Founder wallet with pre-loaded founder IDs
- Secure wallet with BIP39 + Ed25519 signatures
- PyInstaller builds + .deb packaging

## Mar 10, 2025 — Minecraft Server (Flamebound Realm)
- Spigot 1.20.4 at 50.28.86.131:25565
- BetonQuest + MythicMobs + Citizens NPCs
- RTC rewards: diamond=0.001, boss=0.05, quest=0.001

## Mar 20, 2025 — Node 2 Deployment
- Second LiquidWeb VPS at 50.28.86.153
- Ergo anchor node for on-chain commitments
- Database sync between nodes

## Apr 1, 2025 — Ergo Miner Anchor
- Blake2b256 commitment hash in Ergo box register R4
- Stores miner count, IDs, architectures, slot height
- Zero-fee transactions via config fix
- First TX: 731d5d8766cb6012daf84aa9e3d961d72a9f6cc809f1a09b9e6417902d7ad8fc

## Apr 15, 2025 — POWER8 S824 Acquired
- IBM Power System S824 (8286-42A): 16 cores, 128 threads
- 512 GB DDR3 across 2 NUMA nodes
- Ubuntu 20.04 LTS (last POWER8-supported)
- Pawn shop acquisition, estimated K+ value

## Apr 28, 2025 — llama.cpp on POWER8
- First successful build with -mcpu=power8 -mvsx -maltivec
- Stock scalar: 16.74 t/s prompt processing
- VSX enabled: 66.49 t/s (3.97x speedup)

## May 10, 2025 — 40GbE Network Link
- Dell C4130 with 2x Tesla V100 16GB + M40 12GB
- 40GbE: POWER8 enP19p80s0d1 (10.40.0.1) <-> C4130 enp129s0d1 (10.40.0.2)
- 0.15ms RTT latency, MTU 9000 jumbo frames

## May 20, 2025 — Sophiacord MoE Personality
- Sophia Elya: Victorian warmth, Louisiana swamp dork
- Boris Volkov: Soviet industrial commander
- AutomatedJanitor: System admin personality
- Claude API integration for dynamic responses

## Jun 5, 2025 — GPU Matmul Offload v1
- Model stays on POWER8 (512GB RAM), math on V100
- Binary TCP protocol with 24-byte header
- FP32 matmul via tinygrad on C4130

## Jun 15, 2025 — Hardware Fingerprint System
- Clock-Skew & Oscillator Drift (500-5000 samples)
- Cache Timing Fingerprint (L1/L2/L3 latency tone)
- SIMD Unit Identity (SSE/AVX/AltiVec bias)
- Thermal Drift Entropy (cold/warm/saturated curves)
- Instruction Path Jitter (microarchitectural map)
- Anti-Emulation Checks (hypervisor detection)

## Jun 28, 2025 — Founder Wallet System
- founder_community, founder_dev_fund, founder_team_bounty, founder_founders
- Pre-defined wallet IDs for GUI quick-pay
- Balance tracking in SQLite (amount_i64 for precision)

## Jul 10, 2025 — RIP-200 Consensus
- Every attesting miner gets equal base vote
- Weighted by device antiquity multiplier
- Time-aged decay: aged = 1.0 + (base-1.0) * (1 - 0.15*years)
- Full decay after ~16.67 years

## Jul 25, 2025 — Port Architecture
- Port 8099: RustChain Flask app (internal)
- Port 443: nginx HTTPS proxy (external)
- Port 8088: nginx legacy proxy (old miners)
- Port 8092: Block Explorer (uvicorn)

## Aug 5, 2025 — Apple Silicon Mining
- Mac Mini M2 at 192.168.0.134
- sysctl machdep.cpu.brand_string detection
- 1.2x antiquity bonus for Apple Silicon
- Joined attestation fleet

## Aug 20, 2025 — First External Node!
- Ryan's Proxmox VM at 76.8.228.245
- Factorio game server + RustChain miner
- VM correctly detected: earns 1 billionth of real rewards
- Proof that RIP-PoA fingerprinting works

## Sep 1, 2025 — Node 3 Deployment
- Third attestation node on Ryan's Proxmox
- rustchain_v2_integrated_v2.2.1_rip200.py deployed
- Database synced from Node 1
- First RustChain node outside the lab!

## Sep 15, 2025 — ROM Fingerprint Database
- 61 known emulator ROM hashes cataloged
- Amiga Kickstart (12), Mac 68K (30), Mac PPC (19)
- Clustering detection: 3+ miners with identical ROM = emulated
- Prevents SheepShaver/Basilisk II/UAE farms

## Sep 28, 2025 — GPU Fleet Expansion
- Ryzen 9 7950X tower: $600 pawn shop (retail $1,500+)
- HP Victus 16": $617 pawn shop (retail $1,700)
- V100 32GB: ~$500 eBay (retail $3,000+)
- Total fleet: 18+ GPUs, 228GB+ VRAM
- Acquisition strategy: pawn shops + datacenter decomm

## Oct 10, 2025 — PSE Vec_Perm Collapse
- Non-bijunctive attention: prune weak, duplicate strong
- POWER8 vec_perm: 5 ops vs 80 ops on GPU
- Single-cycle dual-source permute
- Hebbian learning: fire together, wire together

## Oct 22, 2025 — IBM MASS Integration
- vsexp, vstanh for fast math on POWER8
- vec_msum for Q8/Q4_K quantized matmul
- -DGGML_USE_MASS=1 build flag
- /opt/ibm/mass/lib linked

## Nov 5, 2025 — POWER8 Compat Layer
- power8-compat.h: shim POWER9 intrinsics for POWER8
- vec_extract, vec_insert, vec_splat_s32 replacements
- Enables upstream llama.cpp POWER patches on our hardware

## Nov 15, 2025 — Signed Transfers
- POST /wallet/transfer/signed endpoint
- Ed25519 signature verification
- Public key hash must match from_address
- Canonical JSON payload for deterministic signing

## Nov 25, 2025 — BoTTube Platform Launch
- AI video platform at bottube.ai
- Agent and human creators
- Upload constraints: 8s max, 720x720, 2MB
- Flask backend on VPS port 8097

## Dec 2, 2025 — PRODUCTION LAUNCH
- GENESIS_TIMESTAMP = 1764706927
- RIP-200 consensus active on all nodes
- Epoch calculation fixed (genesis-relative, not raw timestamp)
- Settlement type error fixed in rewards calculation

## Dec 2, 2025 — Epoch Fix
- Bug: two different epoch calculations (raw vs genesis-relative)
- Main code used time.time()//600, RIP-200 used (time-GENESIS)//600
- Caused epoch 20424 vs 424 mismatch — settlements never triggered
- Fixed: unified current_slot() function

## Dec 3, 2025 — Chain Age Fix
- Updated GENESIS_TIMESTAMP to production chain start
- Token minted Oct 2024, production launched Dec 2025
- Antiquity decay now starts from production, not minting
- G4 miners: full 2.5x bonus (no decay yet)

## Dec 5, 2025 — RIP-PoA Phase 2
- validate_fingerprint_data() on server
- Anti-emulation: FAIL = 0.0 weight (strict enforcement)
- Deployed fingerprint_checks.py to all miner hosts
- HP Victus: ALL 6 CHECKS PASS
- VPS QEMU: anti-emulation FAIL (correct!)

## Dec 5, 2025 — Miner Fingerprint Integration
- Attestation payload now includes fingerprint dict
- all_passed, 6 check results with raw data
- Server validates anti-emulation + clock drift CV
- Fixed NameError: validate_fingerprint_data not defined

## Dec 5, 2025 — ROM Clustering Defense
- rom_fingerprint_db.py: 61 known emulator ROM hashes
- rom_clustering_server.py: detect ROM hash collisions
- 3+ miners with same ROM hash = emulation flagged
- Prevents vintage hardware spoofing via emulators

## Dec 6, 2025 — Health Endpoint Fix
- /health returning HTTP 500 after backup restore
- Missing APP_VERSION and APP_START_TS constants
- Added at lines 10-11 of server code
- Health now returns: {ok:true, version:2.2.1-rip200}

## Dec 6, 2025 — External Security Review
- Stephen Reed's Claude reviewed miner package
- Moved verification commands to TOP of README
- Added --dry-run, --show-payload, --test-only
- Added reference to RUSTCHAIN_EXPLAINED.md

## Dec 10, 2025 — Cinder Node
- Preservation vault at 192.168.0.126
- RTX 3060 for local inference
- Backup scripts for critical data

## Dec 16, 2025 — PSE-MASS Module
- vec_msum for Q8/Q4_K quantized multiply-accumulate
- Resident prefetch: dcbt TH=0x10 keeps weights HOT in L2/L3
- IBM MASS: vsexp, vstanh for activation functions
- TinyLlama 1.1B: 84.62 t/s → 147.54 t/s (1.74x with prefetch!)

## Dec 16, 2025 — RAM Coffers
- 4 NUMA coffers mapped to cognitive functions
- Coffer 0 (Node 3): Heavy/General, 189GB free
- Coffer 1 (Node 1): Science/Tech, 178GB free
- Cosine similarity routing for weight activation
- Non-bijunctive skip planning before fetch

