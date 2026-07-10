# Mine Your Grandma's Computer: Vintage Hardware Setup Guide

Got an old laptop gathering dust or a legacy desktop in a drawer? Instead of throwing it away, you can onboard it to secure the Rustchain network and earn RTC passively. 

Thanks to Rustchain’s unique consensus, vintage hardware is actively rewarded for its architecture. This step-by-step guide will take you from a dusty closet find to earning RTC in under 15 minutes.

---

## 🧐 Does My Computer Qualify? (Quick Check)

Before setting up, make sure your legacy device meets these basic requirements:
* **CPU:** Legacy x86 or certified legacy architectures (Core 2 Duo, Pentium series, or PowerPC).
* **RAM:** Minimum 512MB (1GB or more recommended).
* **Network:** Working Wi-Fi or Ethernet connection to access the internet.
* **OS:** Windows XP/7/10, Linux (Ubuntu/Debian-based), or legacy macOS.

> ⚠️ **Important Anti-Farm Notice:** Modern single-board computers like the **Raspberry Pi** do not qualify as vintage hardware. To prevent bot-farms, modern ARM devices are subject to an anti-farm penalty baseline of **0.0005x**. Stick to authentic legacy desktop/laptop silicon for optimal earnings.

### Official Antiquity Multiplier Scale
Unlike traditional Proof-of-Work systems that favor modern raw hashing power, Rustchain rewards hardware diversity. The exact multipliers configured in the network core (`node/rip_200_round_robin_1cpu1vote.py`) are detailed below:

| Architecture / CPU | Antiquity Multiplier Status |
| :--- | :--- |
| **PowerPC G4 (Legacy Mac)** | `2.5x` Multiplier |
| **Intel Core 2 Duo (Classic Era)** | `1.3x` Multiplier |
| **Modern ARM (Raspberry Pi, etc.)** | `0.0005x` Anti-Farm Penalty |
| **Standard Modern CPU (2016+)** | `1.0x` Baseline |

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
   
