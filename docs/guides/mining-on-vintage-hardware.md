# "Mine Your Grandma's Computer": A Guide to Earning RTC on Vintage Hardware

Got an old computer gathering dust? That closet relic or forgotten laptop could be earning you RTC right now! This guide will get you from "I found an old computer" to "it's earning RTC" in under 15 minutes.

We believe in putting old hardware to good use. In fact, our network rewards older machines with an **Antiquity Multiplier**—a special bonus just for being a classic. Let's get started!

---

### Part 1: Does My Computer Qualify? A Quick Check

Most computers from the last 15-20 years will work. Here’s a quick checklist:

**✅ Minimum Requirements:**
*   **Processor (CPU):** Any 64-bit processor is great (like Intel Core 2 Duo, AMD Athlon 64). Many 32-bit processors also work (like Intel Pentium 4). If you're not sure, just try it!
*   **Memory (RAM):** At least 512MB. 1GB or more is recommended.
*   **Operating System (OS):**
    *   Windows 7 or newer
    *   A common Linux distribution (like Ubuntu, Debian, Mint)
    *   Raspberry Pi OS
*   **Internet:** A stable internet connection (WiFi or Ethernet cable).

**How to Check Your Computer's Specs:**

*   **On Windows:**
    1.  Click the **Start Menu**.
    2.  Right-click on `Computer` or `This PC`.
    3.  Select `Properties`.
    4.  You'll see your Processor, RAM, and whether you have a 32-bit or 64-bit operating system.

    *[Image: Screenshot of the Windows 7/10 System Properties window showing CPU, RAM, and System type.]*

*   **On Linux or Raspberry Pi:**
    1.  Open the **Terminal**.
    2.  Type `lscpu | grep "Architecture"` to see if you have a 32-bit (`i686`) or 64-bit (`x86_64`, `aarch64`) system.
    3.  Type `free -h` to see your total RAM.

    *[Image: Screenshot of a Linux terminal showing the output of `lscpu` and `free -h` commands.]*

---

### Part 2: The 15-Minute Setup

Choose the guide for your type of computer.

#### A. Old Windows Laptop/Desktop

1.  **Download the Miner:**
    *   Go to our official downloads page: `https://rtccoin.network/downloads`
    *   Download the latest Windows `rtc-miner`. Choose the `64-bit.zip` if your system is 64-bit, or `32-bit.zip` if it's 32-bit.

2.  **Unzip the Files:**
    *   Find the downloaded `.zip` file in your `Downloads` folder.
    *   Right-click it and choose `Extract All...`.
    *   Choose a location and click `Extract`. A new folder will be created.

    *[Image: Photo of right-clicking a .zip file on a vintage Windows 7 laptop with "Extract All..." highlighted.]*

3.  **Configure Your Wallet:**
    *   Inside the new folder, find the file named `start.bat`.
    *   Right-click `start.bat` and select `Edit`. It will open in Notepad.
    *   Replace `YOUR_WALLET_ADDRESS_HERE` with your actual RTC wallet address.
    ```batch
    rtc-miner.exe --wallet YOUR_WALLET_ADDRESS_HERE
    pause
    ```
    *   Save the file (`File -> Save`) and close Notepad.

4.  **Run the Miner!**
    *   Double-click the `start.bat` file.
    *   A black command window will appear. Windows Firewall might ask for permission. Click `Allow access`.
    *   That's it! The miner is now running.

    *[Image: Screenshot of the Windows Firewall prompt asking to allow access for `rtc-miner.exe`.]*

#### B. Old Linux Desktop (Pentium 4 / Athlon 64)

1.  **Open the Terminal.** (Usually `Ctrl+Alt+T`)

2.  **Download and Extract:** Run these commands one by one. Copy and paste them into your terminal and press Enter.

    ```bash
    # For 64-bit systems (like Athlon 64):
    wget https://rtccoin.network/downloads/rtc-miner-linux-amd64.tar.gz
    tar -xvf rtc-miner-linux-amd64.tar.gz
    cd rtc-miner-linux-amd64

    # --- OR ---

    # For 32-bit systems (like Pentium 4):
    wget https://rtccoin.network/downloads/rtc-miner-linux-386.tar.gz
    tar -xvf rtc-miner-linux-386.tar.gz
    cd rtc-miner-linux-386
    ```

3.  **Run the Miner!**
    *   Now, run the miner with your wallet address. Replace the placeholder with your address.
    ```bash
    ./rtc-miner --wallet YOUR_WALLET_ADDRESS_HERE
    ```
    *   The miner will start running directly in your terminal.

#### C. Raspberry Pi

The steps are nearly identical to the Linux Desktop.

1.  **Open the Terminal.**

2.  **Download and Extract:** First, check your Pi's architecture with `uname -m`. It will likely be `armv7l` (32-bit) or `aarch64` (64-bit).

    ```bash
    # For 64-bit Raspberry Pi OS:
    wget https://rtccoin.network/downloads/rtc-miner-linux-arm64.tar.gz
    tar -xvf rtc-miner-linux-arm64.tar.gz
    cd rtc-miner-linux-arm64

    # --- OR ---

    # For 32-bit Raspberry Pi OS:
    wget https://rtccoin.network/downloads/rtc-miner-linux-armv7l.tar.gz
    tar -xvf rtc-miner-linux-armv7l.tar.gz
    cd rtc-miner-linux-armv7l
    ```

3.  **Run the Miner!**
    *   Just like on Linux, run the miner with your wallet address.
    ```bash
    ./rtc-miner --wallet YOUR_WALLET_ADDRESS_HERE
    ```

---

### Part 3: Verifying Your Success

After starting, the miner will print messages to the screen. Here’s what to look for.

#### The Fingerprint Check

First, the miner securely identifies your hardware. You should see messages like this:

```
INFO [miner] Starting hardware fingerprinting...
INFO [miner] CPU: Genuine Intel(R) CPU T2300 @ 1.66GHz
INFO [miner] RAM: 2048MB
INFO [miner] Motherboard: Dell Inc. 0FF222
INFO [miner] Fingerprint generated: vintage_intel_core2_dell_...
INFO [network] Submitting fingerprint for verification...
INFO [network] Fingerprint check PASSED!
```

*[Photo: A dusty Core 2 Duo laptop screen showing the terminal with the "Fingerprint check PASSED!" message.]*

#### Your First Attestation

An "attestation" is a small job your computer completes to help the network. Once you pass the fingerprint check, you'll start receiving them. A successful one looks like this:

```
INFO [miner] Attestation challenge received. Starting work...
INFO [miner] Work complete in 4.72s. Submitting attestation.
SUCCESS [network] Attestation accepted! Reward: 0.5 RTC (+0.25 antiquity bonus)
```
Congratulations! You are now officially earning RTC.

*[Photo: The same laptop screen, now showing the "Attestation accepted!" message with a visible antiquity bonus.]*

---

### Part 4: What is the "Antiquity Multiplier"?

In plain English: **It's a bonus for using old hardware.**

Think of it like a classic car. A 1969 Mustang is special because of its age and history. In our network, we think a 2006 Dell laptop is special for the same reason!

The network identifies the age of your computer's main components (like its CPU). The older your hardware, the bigger the bonus multiplier you get on every single reward. It's our way of thanking you for saving cool old tech from the landfill and making our network more diverse and robust.

---

### Bonus: 2-Minute Video Walkthrough

Prefer to watch a video? We've got you covered. Here's a complete walkthrough of the setup process on an old Windows laptop.

**▶️ [Watch the 2-Minute Guide on YouTube](https://rtccoin.network/video-guide)**

---

### Troubleshooting

*   **"Permission denied" on Linux/Raspberry Pi?**
    *   You might need to make the file executable. Run this command: `chmod +x rtc-miner` and try running it again.
*   **Where do I get an RTC Wallet?**
    *   You can create a new wallet by following our [Wallet Setup Guide](https://rtccoin.network/guides/wallet-setup).
*   **Is it safe to run this?**
    *   Yes. Always download the miner from our official links. The miner only uses your CPU for computations and does not access your personal files.
