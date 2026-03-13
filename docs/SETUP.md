# PS1 Miner Hardware Setup

## Overview

The PS1 miner communicates with a PC via serial connection. The PC acts as a bridge to the RustChain network.

```
┌─────────────┐     Serial Cable     ┌─────────────┐
│ PlayStation │◄────────────────────►│    PC       │
│     PS1     │    TX, RX, GND       │  (Bridge)   │
│  (Miner)    │                      │  → Node     │
└─────────────┘                      └─────────────┘
```

## Required Hardware

### 1. PlayStation 1

Any model works:
- **SCPH-1000/1001/1002** (original fat)
- **SCPH-5000/5500/5903** (PSone)
- Modded or with FreeMcBoot for running homebrew

### 2. Serial Adapter

**Option A: USB-to-TTL Serial Adapter** (Recommended)
- CP2102, CH340, or FTDI based
- 3.3V or 5V logic
- Cost: ~$5-10

**Option B: Null Modem Cable**
- DB9 female to DB9 female
- Requires PC with serial port
- Cost: ~$10-15

### 3. Wiring

#### USB-to-TTL to PS1 Controller Port

The PS1 controller port has serial capability!

```
USB-TTL     PS1 Controller Port (SCPH-1040 adapter)
--------    ---------------------------------------
GND    ──── Pin 1 (GND)
TX     ──── Pin 3 (RX)
RX     ──── Pin 2 (TX)
```

**Pinout (PS1 Controller Port):**
```
  ┌─────────────────┐
  │ 1 2 3 4 5 6 7   │  Top view
  └─────────────────┘
  
  Pin 1: GND
  Pin 2: TX (from PS1)
  Pin 3: RX (to PS1)
  Pin 4: Unknown
  Pin 5: +3.3V (DO NOT CONNECT!)
  Pin 6: Select
  Pin 7: +3.3V (DO NOT CONNECT!)
```

**⚠️ WARNING:** Do NOT connect the +3.3V pins! Only use GND, TX, and RX.

#### Alternative: Parallel Port

Some PS1 models support parallel I/O (SCPH-1040 cable).

```
Parallel Port → USB Parallel Adapter → PC
```

This provides faster communication but requires more complex wiring.

## Software Setup

### PC Side (Bridge)

1. **Install Python 3.8+**
   ```bash
   python --version
   ```

2. **Install dependencies**
   ```bash
   cd ps1_bridge
   pip install -r requirements.txt
   ```

3. **Find serial port**
   ```bash
   # Windows
   python bridge.py --list-ports
   
   # Linux
   ls /dev/ttyUSB* /dev/ttyS*
   ```

4. **Run bridge**
   ```bash
   # Windows (COM3)
   python bridge.py -p COM3 -w ps1-miner
   
   # Linux (/dev/ttyUSB0)
   python bridge.py -p /dev/ttyUSB0 -w ps1-miner
   ```

### PS1 Side (Miner)

1. **Build the miner** (see BUILD.md)
   ```bash
   cd ps1_miner
   make
   ```

2. **Transfer to PS1**
   - Via link cable: `make install`
   - Via memory card: Copy `.bin` to card
   - Via CD-R: Burn and run on modded PS1

3. **Run the miner**
   - Load via FreeMcBoot or homebrew launcher
   - Miner will auto-detect serial connection

## Configuration

### Bridge Configuration

Edit `ps1_bridge/config.json`:
```json
{
  "serial_port": "COM3",
  "baud_rate": 9600,
  "wallet_name": "ps1-miner",
  "node_url": "https://rustchain.org"
}
```

### Miner Configuration

The miner stores config on the memory card:
- `bu00:RUSTCHN/WALLET.DAT` - Wallet ID
- `bu00:RUSTCHN/CONFIG.DAT` - Settings

## Testing Connection

### Loopback Test (PC Side)

```python
import serial

ser = serial.Serial('COM3', 9600, timeout=1)

# Connect TX to RX on the adapter
# Any character sent should be received back
ser.write(b'HELLO\n')
response = ser.readline()
print(f"Received: {response}")
```

### PS1 Serial Test

Run the miner - it will print serial initialization messages:
```
[SERIAL] Initialized at 9600 bps
```

If you see garbled text:
- Check baud rate matches
- Verify TX/RX are not swapped
- Ensure GND is connected

## Troubleshooting

### "Port not found"
- Check device manager (Windows) or `dmesg` (Linux)
- Try a different USB port
- Install adapter drivers

### "No response from PS1"
- Verify wiring (TX↔RX crossover)
- Check that PS1 miner is running
- Try different baud rate

### "Attestation rejected"
- Ensure wallet is registered
- Check network connectivity
- Verify node URL

### Garbled output
- Baud rate mismatch
- Wrong serial settings (8N1)
- Loose connections

## Expected Output

### PS1 Console Output
```
RustChain PS1 Miner v0.1.0
MIPS R3000A @ 33.87 MHz | 2 MB RAM
Antiquity Multiplier: 2.8x
========================================

Wallet: abc123...RTC

Running hardware fingerprint checks...
Fingerprint collected successfully.
  BIOS: Sony Computer Entertainment...
  CD-ROM timing: 15234 cycles
  RAM timing: 45000 ns

Starting attestation cycles...
Press SELECT to exit

[Epoch 0] Starting attestation...
Sending: ATTEST:{...}
Response: OK
Attestation successful!
```

### PC Bridge Output
```
[BRIDGE] Connected to PS1 on COM3 @ 9600 bps
[BRIDGE] Starting PS1 Bridge...
[BRIDGE] Node: https://rustchain.org
[BRIDGE] Wallet: ps1-miner

[PS1] <- ATTEST:{"wallet":"abc123...","epoch":0,...}
[BRIDGE] Attestation accepted! Reward: 0.042 RTC
[BRIDGE] -> RESULT:OK
```

## Safety Notes

1. **Never connect power pins** - PS1 controller port has +3.3V
2. **Use current-limited USB port** - Protects against shorts
3. **Double-check wiring** before powering on
4. **Use ESD protection** when handling electronics

## Next Steps

1. ✅ Hardware connected
2. ✅ Software running
3. 📄 See TROUBLESHOOTING.md for issues
4. 🎮 Start mining on PS1!

---

*"Every CPU deserves dignity" — Even a 30-year-old game console.* 🦀🎮
