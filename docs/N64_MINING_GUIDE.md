# Mining RTC on a Nintendo 64

> A 1996 MIPS R4300i earns **3.0x** what a modern Threadripper earns. Here is how to set it up.

---

## What You Need

| Component | Cost | Purpose |
|-----------|------|---------|
| Nintendo 64 console | $40-80 used | The miner itself (NEC VR4300 MIPS CPU) |
| EverDrive 64 X7 (or clone) | $50-100 | Loads the mining ROM from SD card |
| Raspberry Pi Pico | $4 | Serial bridge between N64 controller port and PC |
| USB Micro-B cable | $3 | Connects Pico to host PC |
| Controller port adapter cable | $5 DIY | Wires from N64 controller port to Pico GPIO |
| SD card (any size) | $5 | Holds the mining ROM for EverDrive |
| PC or laptop running Linux/macOS/Windows | -- | Runs the Python host relay to RustChain node |

**Total cost: approximately $60-100 if you already own an N64.**

Optional but recommended:
- Pico W ($6) for standalone WiFi mining without a host PC
- Power strip with switch for easy on/off
- A copy of Legend of Elya to earn achievement-based RTC alongside mining rewards

---

## Architecture Overview

```
 Nintendo 64                     Pico Bridge              Host PC
 ┌──────────────┐              ┌─────────────┐        ┌──────────────────┐
 │ NEC VR4300   │  Controller  │ RP2040      │  USB   │ Python relay     │
 │ MIPS R4300i  │──  Port   ──│ Serial      │── ─ ──│ n64_llm_bridge.py│
 │ 93.75 MHz    │  (1-wire)   │ bridge      │ serial │                  │
 │              │              │ main.cpp    │        │  ┌──────────┐   │
 │ mining ROM   │              └─────────────┘        │  │ RustChain│   │
 │ on EverDrive │                                      │  │ node     │   │
 └──────────────┘                                      │  │ :8099    │   │
                                                       └──┴──────────┴───┘
```

**Data flow:**
1. Host PC sends a challenge nonce over USB serial to the Pico
2. Pico relays the nonce to the N64 via the controller port protocol
3. N64 CPU computes SHA-256(nonce || wallet_id) using its MIPS FPU
4. N64 sends the result back through the controller port to the Pico
5. Pico forwards the hash + timing data over USB serial to the host
6. Host submits the attestation to the RustChain node at `https://rustchain.org`

The N64 controller port uses a single-wire serial protocol at 250 kHz. The Pico handles the low-level bit-banging and translates to standard USB serial.

---

## Step 1: Flash the Mining ROM

### Download

```bash
# Clone the Legend of Elya N64 repository
git clone https://github.com/Scottcjn/legend-of-elya-n64.git
cd legend-of-elya-n64/mining/
```

The mining ROM is `legend_of_elya_mining.z64`. It contains:
- A minimal MIPS bootloader that initializes the N64 hardware
- SHA-256 implementation using the VR4300 hard float unit
- Controller port I/O routines for Pico communication
- Hardware fingerprint self-test routines (PRId register, COUNT timing, etc.)

### Copy to EverDrive

1. Insert the SD card into your PC
2. Copy `legend_of_elya_mining.z64` to the root of the SD card
3. Eject the SD card and insert it into the EverDrive 64
4. Insert the EverDrive into the N64 cartridge slot

### Verify

Power on the N64. The screen should display:

```
RUSTCHAIN MINING ROM v1.0
VR4300 @ 93.75 MHz
Waiting for Pico bridge...
```

If you see this, the ROM loaded correctly. The N64 will idle until the Pico bridge connects.

---

## Step 2: Wire the Pico Bridge

### N64 Controller Port Pinout

```
N64 Controller Port (male, looking at console)
┌─────────┐
│ 1  2  3 │
│         │
│    4    │
└─────────┘

Pin 1: Data   → Pico GPIO 2
Pin 2: Unused → NC (no connection)
Pin 3: GND    → Pico GND
Pin 4: VCC    → Pico VBUS (5V, powers Pico from N64)
```

Use 22-26 AWG wire. Solder or use a sacrificed controller extension cable for the connector.

### Flash the Pico Firmware

```bash
cd legend-of-elya-n64/bridge/pico/

# Install dependencies (PlatformIO or Arduino IDE)
# PlatformIO method:
pip install platformio
pio run --target upload --upload-port /dev/ttyACM0

# Arduino IDE method:
# 1. Open main.cpp as a .ino file
# 2. Board: Raspberry Pi Pico
# 3. Upload
```

The Pico firmware (`main.cpp`) handles:
- N64 single-wire protocol at 250 kHz (3.3V logic, compatible with N64's 3.3V data line)
- USB CDC serial at 115200 baud to the host PC
- Challenge/response relay between host and N64
- Timing measurement of N64 hash computation (used for fingerprinting)

### Verify the Bridge

```bash
# Open serial monitor (Linux)
screen /dev/ttyACM0 115200

# You should see:
# PICO_READY|RIP-0683 N64 Bridge v1.0|
```

---

## Step 3: Set Up the Python Host Relay

The host relay runs on any PC with Python 3.8+ and a USB port.

```bash
cd legend-of-elya-n64/bridge/host/

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install pyserial requests

# Configure
cp config.example.json config.json
```

Edit `config.json`:

```json
{
  "wallet_id": "my-n64-miner",
  "node_url": "https://rustchain.org",
  "serial_port": "/dev/ttyACM0",
  "serial_baud": 115200,
  "attest_interval_seconds": 300,
  "console_type": "n64_mips"
}
```

### Start Mining

```bash
python3 n64_llm_bridge.py
```

Expected output:

```
[N64 Bridge] Connected to Pico on /dev/ttyACM0
[N64 Bridge] N64 detected: VR4300 MIPS R4300i
[N64 Bridge] Wallet: my-n64-miner
[N64 Bridge] Node: https://rustchain.org
[N64 Bridge] Attestation interval: 300s
[N64 Bridge] --- First attestation ---
[N64 Bridge] Sent nonce: a7f3c2...
[N64 Bridge] N64 hash time: 847ms (real MIPS silicon)
[N64 Bridge] Attestation submitted: HTTP 200
[N64 Bridge] Device arch: n64_mips | Multiplier: 3.0x
[N64 Bridge] Next attestation in 300s...
```

### Run as a Service (Linux)

```bash
# Create systemd service
sudo tee /etc/systemd/system/n64-miner.service << 'EOF'
[Unit]
Description=RustChain N64 Miner Bridge
After=network-online.target

[Service]
Type=simple
User=scott
WorkingDirectory=/home/scott/legend-of-elya-n64/bridge/host
ExecStart=/home/scott/legend-of-elya-n64/bridge/host/venv/bin/python3 n64_llm_bridge.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now n64-miner
```

---

## The 5 Hardware Fingerprint Checks on N64

The N64 must pass 5 checks to prove it is real silicon, not an emulator like Project64 or Mupen64Plus.

### 1. PRId Register (Processor Revision Identifier)

The VR4300 reports its silicon revision via the MIPS CP0 PRId register. Real N64 CPUs report `0x00000B22` (VR4300 rev 2.2). Emulators often return incorrect or generic values.

### 2. COUNT Register Timing

The MIPS COUNT register increments at half the CPU clock (46.875 MHz on N64). The mining ROM samples COUNT at microsecond intervals and measures the coefficient of variation. Real silicon has measurable oscillator drift (CV > 0.001). Emulators tied to the host clock show CV < 0.0001.

### 3. VI (Video Interface) Scanline Timing

The N64 VI generates interrupts at each scanline. Real hardware has per-scanline jitter of 10-50 ns due to the RCP (Reality Coprocessor) bus arbitration. Emulators simulate scanlines at perfectly uniform intervals.

### 4. RDRAM Timing Ratio

The N64 uses Rambus RDRAM at 500 MHz. The ratio of RDRAM access latency to CPU cache latency is characteristic of real hardware (approximately 18:1). Emulators that simulate RDRAM flatten this ratio to near 1:1.

### 5. Anti-Emulation Behavioral Checks

The ROM runs a battery of operations that behave differently on real hardware vs emulators:
- TLB (Translation Lookaside Buffer) miss timing
- Unaligned memory access penalty
- Branch delay slot execution timing
- RCP-to-CPU DMA transfer jitter

If an emulator is detected, the attestation still submits but the miner receives the VM penalty rate (0.000000001x instead of 3.0x).

---

## Multiplier and Expected Earnings

The N64's NEC VR4300 is a 1996 MIPS chip. Under RIP-200 Proof of Antiquity:

| Parameter | Value |
|-----------|-------|
| Base multiplier | 3.0x (MIPS R4000 family, 1996) |
| Time decay | -0.15 per year of chain age |
| Current chain age | ~0.3 years (chain launched Dec 2025) |
| Current effective multiplier | ~2.96x |
| Epoch reward pool | 1.5 RTC per epoch (10 minutes) |

**Example earnings** (assuming 10 miners in the epoch, equal uptime):

```
N64 share:   2.96 / total_weight * 1.5 RTC
With 10 miners at avg 1.5x weight:
  Total weight = 15.0
  N64 share = (2.96 / 15.0) * 1.5 = 0.296 RTC per epoch
  Daily: ~42.6 RTC (at 144 epochs/day)
```

Your actual earnings depend on how many miners are attesting and their multipliers. Check the live epoch data:

```bash
curl -sk https://rustchain.org/epoch
curl -sk "https://rustchain.org/wallet/balance?miner_id=my-n64-miner"
```

---

## Playing Legend of Elya for Achievement RTC

Mining is passive. But you can also **play** the Legend of Elya N64 game and earn additional RTC through the achievement system.

The [rustchain-arcade](https://github.com/Scottcjn/rustchain-arcade) repository implements a RetroAchievements-style bridge for retro gaming on real hardware:

1. **Play the game** on your N64 via EverDrive
2. **Achievements unlock** as you progress (defeat bosses, find items, complete quests)
3. **The Pico bridge detects achievements** by monitoring memory addresses via the controller port
4. **Achievement events are submitted** to the RustChain node alongside mining attestations
5. **Proof of Play bonus**: 1.5x-5.0x multiplier on top of your mining rewards for the epoch where the achievement occurred

| Achievement | RTC Bonus | Proof of Play Multiplier |
|-------------|-----------|--------------------------|
| First dungeon cleared | 0.05 RTC | 1.5x |
| Boss defeated | 0.10 RTC | 2.0x |
| Rare item found | 0.02 RTC | 1.5x |
| Game completed | 1.00 RTC | 5.0x |

This is "play to earn" on 1996 hardware. The game is the mining software.

### Set Up the Achievement Bridge

```bash
git clone https://github.com/Scottcjn/rustchain-arcade.git
cd rustchain-arcade

pip install -r requirements.txt

# Configure for N64
cp config.example.yaml config.yaml
# Edit config.yaml: set console=n64, serial_port, wallet_id

python3 achievement_bridge.py
```

The achievement bridge runs alongside the mining relay. Both use the same Pico serial connection.

---

## Troubleshooting

### N64 shows black screen after loading ROM
- Verify the ROM file is not corrupted: `sha256sum legend_of_elya_mining.z64`
- Ensure the EverDrive firmware is up to date
- Try a different SD card (some N64 EverDrives are picky about card speed)

### Pico not detected on USB
- Try a different USB cable (data cables, not charge-only)
- Check `ls /dev/ttyACM*` (Linux) or Device Manager (Windows)
- Re-flash the Pico: hold BOOTSEL while plugging in, then copy the UF2 file

### Attestation returns HTTP 500
- Check that your wallet ID is unique (not already registered to different hardware)
- Verify node connectivity: `curl -sk https://rustchain.org/health`
- Check the host relay log for error details

### N64 hash time is suspiciously fast (< 100ms)
- This likely means the Pico is computing the hash instead of the N64
- Verify the controller port wiring, especially the data line (Pin 1 to GPIO 2)
- The ROM should report hash times of 500-1500ms on real VR4300 silicon

### Fingerprint check fails
- Ensure you are running on a real N64, not an emulator
- FPGA clones (Analogue, MiSTer) are detected as non-original silicon and receive reduced multipliers
- Only original NEC VR4300 silicon gets the full 3.0x multiplier

---

## Further Reading

- [Console Mining Setup Guide](CONSOLE_MINING_SETUP.md) -- covers all supported consoles (NES, SNES, Genesis, PS1, Game Boy, and more)
- [Hardware Fingerprinting](hardware-fingerprinting.md) -- deep dive into the 6+1 fingerprint checks
- [Vintage Mining Explained](VINTAGE_MINING_EXPLAINED.md) -- why we mine on old hardware
- [Boudreaux Computing Principles](Boudreaux_COMPUTING_PRINCIPLES.md) -- the philosophy behind Proof of Antiquity
- [Legend of Elya N64 Repository](https://github.com/Scottcjn/legend-of-elya-n64/tree/main/mining)
- [RustChain Arcade Achievement Bridge](https://github.com/Scottcjn/rustchain-arcade)
- [RustChain Explorer](https://rustchain.org/explorer) -- see your miner live on the network
