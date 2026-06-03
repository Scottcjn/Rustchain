# Mine Your Grandma's Computer: The 15-Minute RustChain Guide

Got an old laptop collecting dust in the closet? Don't throw it away! That vintage hardware is exactly what the **RustChain** network values most. In under 15 minutes, you can turn e-waste into an RTC-earning node.

This guide will take you from "I found an old computer" to "It's earning RTC" using real examples of a **Core 2 Duo Windows Laptop** and a **PowerPC G4 Mac**.

---

## 🛑 Does my computer qualify? (The Quick Check)

RustChain rewards **real silicon**, not raw power. 
If your computer meets these two simple criteria, it qualifies:
1. **It boots an operating system** (Windows XP/7/10, Mac OS X, or Linux).
2. **It can connect to the internet** (Wi-Fi or Ethernet).

**What DOESN'T qualify?**
- Virtual Machines (VMware, VirtualBox, Proxmox). *They earn 0.000000001x rewards.*
- Modern Cloud VPS (AWS, DigitalOcean). *They earn standard base rewards, but cost more than they earn.*

---

## 📈 The Antiquity Multiplier (Explained in Plain English)

Why use an old computer instead of a brand new gaming PC? 
**The Antiquity Multiplier.**

RustChain is designed to preserve computing history. The older and weirder your computer's processor is, the more RTC you earn per epoch:
- **Modern PC (Core i9):** 0.8x rewards
- **Old Core 2 Duo Laptop (2006):** 1.3x rewards
- **Power Mac G4 (2003):** 2.5x rewards

A 20-year-old PowerBook G4 will earn **more than three times** the RTC of a brand new $3,000 gaming desktop! 

---

## 🛠️ Walkthrough 1: The Core 2 Duo Windows Laptop (2006-2009 Era)

*Example Hardware: Dell Inspiron 1520 or ThinkPad T61*

### Step 1: Download the Miner
1. Turn on the laptop and connect to Wi-Fi.
2. Open a web browser and download the latest `win-miner` bundle from the [RustChain Releases page](https://github.com/Scottcjn/Rustchain/releases).
3. Extract the ZIP file to your Desktop.

### Step 2: Create a Wallet (Optional, if you don't have one)
Double-click `rustchain-wallet.exe` and follow the prompts to generate a new wallet address. Save your 12-word recovery phrase safely!

### Step 3: Run the Fingerprint Check
RustChain needs to verify your hardware is real. 
1. Open the extracted folder.
2. Hold `Shift` and right-click in the folder background, then select **"Open command window here"** (or PowerShell).
3. Type: `miner.exe --dry-run` and press Enter.

*(Screenshot: A Windows command prompt showing a successful fingerprint check, with CPU identified as Core 2 Duo and "Hardware Check: PASSED")*
> **Look for this line:** `Fingerprint verification: SUCCESS. Architecture: x86_64 (Core 2 Duo)`

### Step 4: Start Mining!
Double click the `start_mining.bat` file. 
- It will ask for your Wallet Address. Paste it in.
- It will ask for a miner name (e.g., `grandmas-thinkpad`).
- Type `YES` to agree to the consent screen.

*(Screenshot: The miner showing "Attestation submitted successfully" and waiting for the next epoch)*
**Boom. You're earning RTC.**

---

## 🍎 Walkthrough 2: The PowerPC Mac G3/G4/G5 (1997-2005 Era)

*Example Hardware: PowerBook G4 or iMac G3 (Running Mac OS X Leopard or Tiger)*

### Step 1: Get the Python Miner
PowerPC Macs are legendary on RustChain (earning up to 2.5x rewards!). Because they are so old, we use the lightweight Python miner.
1. Open the Terminal application (in `Applications > Utilities`).
2. Clone the repository (or download the ZIP if git isn't installed):
   ```bash
   curl -LO https://github.com/Scottcjn/Rustchain/archive/refs/heads/main.zip
   unzip main.zip
   cd Rustchain-main/miners/linux
   ```

### Step 2: The Fingerprint Check
Run the dry-run to ensure your PowerPC chip is correctly identified by the network.
```bash
python3 miner_threaded.py --dry-run
```
*(Screenshot: A Mac Terminal window showing `sys_vendor: Apple Computer, Inc.`, `Architecture: PowerPC G4`, and `Fingerprint: SUCCESS`)*

### Step 3: Start Attesting
Start the miner in the background!
```bash
python3 miner_threaded.py --wallet YOUR_RTC_WALLET_ADDRESS --name powerbook-g4
```
Type `OUI` (or `YES` depending on your locale) to agree to the consent screen.

*(Screenshot: The terminal displaying "Epoch 1234: Attestation accepted. Multiplier: 2.5x")*

---

## 💡 Pro-Tips for Vintage Mining
- **Keep it cool:** Old laptops get hot. Keep them on a hard surface.
- **Screen timeout:** Set your computer to never go to sleep, but allow the screen to turn off to save power.
- **Check your stats:** Enter your wallet address on the [RustChain Explorer](https://rustchain.org) to watch your vintage hardware rake in the rewards!
