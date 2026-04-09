# Mine Your Grandma's Computer: The RustChain Vintage Hardware Guide
<!-- SPDX-License-Identifier: MIT -->
<!-- BCOS-Tier: L1 -->

## 🛠 Introduction
Got an old laptop in the attic? A PowerBook G4 gathering dust? A Pentium III that hasn't seen electricity since the dot-com bubble? **Don't throw it away.**

RustChain is a Proof-of-Antiquity network that rewards hardware longevity. In this ecosystem, a machine from 1995 can outearn a brand-new Threadripper. This guide will help you resurrect your "vintage iron" and start earning RTC.

---

## 💰 The Economic Case for Vintage
RustChain uses a **Multi-Tiered Antiquity Multiplier**. The older the silicon, the bigger the reward slice.

### Hardware Bounty Tiers
| Era | Typical CPUs | Multiplier | One-time Bounty |
|-----|--------------|------------|-----------------|
| **Museum Grade** (Pre-1985) | MOS 6502, DEC VAX | 3.5x | **300 RTC** |
| **Ultra-Vintage** (1985-1990) | Intel 386, MC68000 | 3.0x | **200 RTC** |
| **Classic Vintage** (1991-1995) | Intel 486, PowerPC 601 | 2.5x | **150 RTC** |
| **Late Vintage** (1996-1999) | Pentium II/III, AMD K6 | 2.0x | **100 RTC** |
| **Modern Relic** (2000-2010) | Pentium 4, PowerPC G4/G5 | 1.5x | Standard Mining |

---

## 🚦 Choosing Your Setup Path

Depending on how "vintage" your grandma's computer is, you have three options:

### 1. The Standard Path (Post-2005)
**Requirement**: Can run Python 3.8+ and has a decent internet connection.
- **Best for**: Pentium 4, G4/G5 Macs running Lubuntu or OS X Leopard.
- **Setup**: Use the [Quickstart Guide](./QUICKSTART.md).

### 2. The Vintage Path (1995-2004)
**Requirement**: Can run Python 3.7+ (supports Windows XP with tweaks).
- **Best for**: Pentium II/III, original iMacs, Windows 98/XP machines.
- **Setup**: Uses the specialized `vintage_miner_client.py`.

### 3. The Hardcore Path (Pre-1995)
**Requirement**: Manual assembly or specialized C code.
- **Best for**: Amiga 500/1200, Commodore 64, VAX stations.
- **Setup**: See [Amiga Tools](../rustchain-poa/tools/amiga/README.md).

---

## 🚀 Setting Up the Vintage Miner (Tier 2/3)

If the standard installer is too heavy for your machine, follow these steps to use the lightweight **Vintage Client**:

### 1. Identify Your Profile
Check the supported profiles by running:
```bash
python3 vintage_miner_client.py --list-profiles
```
Common profiles include `intel_386`, `pentium_ii`, `motorola_68000`, and `powerpc_750`.

### 2. Install Dependencies
The vintage client only requires the `requests` library. If you can't use `pip`, simply download the `requests` source and place it in the same directory.

### 3. Start Mining
Run the miner with your specific profile:
```bash
python3 vintage_miner_client.py --profile [YOUR_PROFILE] --miner-id [YOUR_WALET_NAME] --attest
```
Example:
```bash
python3 vintage_miner_client.py --profile pentium_iii --miner-id grandma-pc --attest
```

---

## 🌡️ Maintenance Checklist for Ancient Iron

Mining generates heat. Before you leave a 25-year-old computer running 24/7:

1.  **Capacitor Check**: Open the case. Look for "leaky" or bulging capacitors. If you see brown crust, do not plug it in.
2.  **The Dust Bunny Hazard**: Use compressed air to clean out decades of dust from CPU heat sinks.
3.  **Fresh Thermal Paste**: If possible, remove the heat sink and replace the dried-out 1990s thermal paste with something modern.
4.  **Power Supply**: Old power supplies (PSUs) can be fire hazards. If it smells like ozone or burning plastic, power down immediately.

---

## 📸 Claiming Your Hardware Bounty

To claim the one-time RTC bounty for your era, you must submit an **Evidence Package**:

1.  Run the client with the evidence flag:
    ```bash
    python3 vintage_miner_client.py --profile [PROFILE] --miner-id [ID] --evidence --output claim.json
    ```
2.  Take a photo of the physical machine running the miner.
3.  Open an issue on the [Bounty Board](https://github.com/Scottcjn/rustchain-bounties/issues) with the title "Hardware Claim: [CPU Model]".
4.  Attach your `claim.json` and the photo.

---

## 📜 Legal & License
<!-- SPDX-License-Identifier: MIT -->
This guide and the associated vintage miner tools are provided "as-is". Elyan Labs is not responsible for any damage to vintage hardware caused by mining heat or power surges.

*Mais, it still works, so let it earn its keep!*
