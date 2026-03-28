# ⛏️ Mastering the RustChain Miner: Hardware Fingerprints & Dual-Mining v2.0

RustChain isn't just another Proof-of-Work (PoW) coin. It uses **RIP-PoA (Hardware Fingerprint Attestation + Serial Binding)** to ensure that one CPU equals one vote, preventing large-scale farm domination.

This guide covers how to set up and optimize the **Linux Ryzen Miner (v2.0)** for maximum efficiency.

---

## 🏗️ 1. The Core Architecture
The miner is built on Python 3 but interacts directly with the Linux kernel via `/sys/class/dmi/` to bind your mining identity to your hardware serial number.

### Hardware Binding
The miner attempts to fetch your serial from:
1. `/sys/class/dmi/id/product_serial`
2. `/sys/class/dmi/id/board_serial`
3. Fallback: `/etc/machine-id` (First 16 characters)

**Tip:** If you are running in a VM, the serial might return `None`. For maximum yield, run on **Bare Metal** to pass the RIP-PoA attestation.

---

## 🛡️ 2. RIP-PoA Fingerprint Checks
To mine on the mainnet, your machine must pass **6 hardware fingerprint checks**. These include:
- **DMI Table Validation:** Ensures the BIOS info matches the CPU architecture.
- **Cache Latency Check:** Detects virtualization or "noisy neighbor" environments.
- **Instruction Set Verifier:** Confirms the presence of required AVX/AES-NI extensions.

If these checks fail, your attestation will be invalid, and your blocks will be rejected by the node.

---

## ⚡ 3. Dual-Mining with Warthog (Sidecar)
The v2.0 miner includes the **WarthogSidecar**. This allows you to mine RustChain (CPU) and Warthog (GPU/CPU) simultaneously without context-switching overhead.

### Configuration
Pass these flags to the `LocalMiner` class or your CLI wrapper:
- `wart_address`: Your Warthog wallet address.
- `wart_pool`: The stratum URL for your preferred Warthog pool.
- `bzminer_path`: Path to your BZminer binary.

---

## 🚀 4. Optimization Tips
- **Python Warnings:** The miner ignores `Unverified HTTPS` warnings for self-signed node certificates. This is normal but ensure your `NODE_URL` is set to `https://rustchain.org`.
- **Entropy Management:** The miner tracks `last_entropy` to ensure your PoW isn't being "pre-calculated" on a different machine.
- **Log Leveling:** Use `color_logs.py` (if available) to visually distinguish between `[FINGERPRINT]` passes and `[PoW]` shares.

---

*Written by RematNOC - Contributing to the RustChain Ecosystem.*
