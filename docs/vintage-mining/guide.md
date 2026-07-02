# Mine Your Grandma's Computer: Vintage Hardware Setup Guide

Got an old laptop gathering dust or an early-generation Raspberry Pi in a drawer? Instead of throwing it away, you can onboard it to secure the Rustchain network and earn RTC passively. 

Thanks to Rustchain’s unique consensus, vintage hardware is actively rewarded for its age. This step-by-step guide will take you from a dusty closet find to earning RTC in under 15 minutes.

---

## 🧐 Does My Computer Qualify? (Quick Check)

Before setting up, make sure your legacy device meets these basic requirements:
* **CPU:** Any legacy x86 or ARM processor (Core 2 Duo, Pentium 4, Athlon 64, PowerPC G3/G4/G5, or Raspberry Pi 2+).
* **RAM:** Minimum 512MB (1GB or more recommended).
* **Network:** Working Wi-Fi or Ethernet connection to access the internet.
* **OS:** Windows XP/7/10, Linux (Ubuntu/Debian-based), or legacy macOS.

### The Antiquity Multiplier Scale
Unlike traditional Proof-of-Work systems that favor raw power, Rustchain rewards hardware diversity. Older machines receive a multiplier applied to baseline attestation rewards:

| Era | CPU Examples | Antiquity Multiplier |
| :--- | :--- | :--- |
| **Ancient (1995-2005)** | Pentium 1-4, Athlon 64, PowerPC G3/G4 | `3.0x - 5.0x` |
| **Classic (2006-2012)** | Core 2 Duo, 1st Gen Core i3/i5 | `2.0x - 3.0x` |
| **Modern Vintage (2013-2015)** | Haswell / Skylake Architectures | `1.5x - 2.0x` |
| **Modern (2016+)** | Current generation chips | `1.0x (Base)` |

---

## 🚀 Setup Profile 1: Windows Laptop (Core 2 Duo Era)

### Step 1: Download the Client
1. Boot up your vintage Windows laptop and connect to the internet.
2. Download the lightweight windows binary: `rustchain-miner-windows-x86.zip`.
3. Extract the contents directly into a root folder, for example: `C:\RustChain\`.

### Step 2: Generate the Hardware Fingerprint
Rustchain analyzes timing characteristics and low-level jitter variance to prove your hardware is real bare metal and genuinely vintage.
1. Open **PowerShell** or **Command Prompt** as an Administrator.
2. Navigate to your directory and run the fingerprint diagnostic:
   ```powershell
   cd C:\RustChain
   .\rustchain-miner.exe --fingerprint
   
