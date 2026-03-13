# PlayStation 1 Miner Port Plan

## Bounty Claim: Issue #430 - Port Miner to PlayStation 1

**Wallet:** `RTC4325af95d26d59c3ef025963656d22af638bb96b`

**Reward:** 150 RTC ($15)

---

## Executive Summary

This document outlines the plan to port the RustChain miner to Sony PlayStation 1 (SCPH-1000/1001/1002 series), making it the **first blockchain miner to run on PS1 hardware**. The PS1 uses a **MIPS R3000A CPU @ 33.87 MHz** with only **2 MB RAM**, presenting unique challenges for blockchain attestation.

### Antiquity Multiplier: **2.8x** (per RIP-304)

---

## PS1 Hardware Specifications

| Component | Specification |
|-----------|---------------|
| **CPU** | MIPS R3000A (32-bit) @ 33.87 MHz |
| **RAM** | 2 MB main + 1 MB VRAM |
| **ROM** | 512 KB BIOS |
| **Storage** | CD-ROM, Memory Card (128 KB) |
| **I/O** | Serial (9600 bps), Parallel, Controller ports |
| **FPU** | Optional CP2 coprocessor (geometry engine) |
| **Endianness** | Little-endian |

---

## Architecture Options

### Option A: Standalone with Serial Bridge (RECOMMENDED)

```
┌─────────────────┐     Serial (9600 bps)     ┌──────────────┐
│  PlayStation 1  │◄─────────────────────────►│  PC Bridge   │
│  (MIPS R3000A)  │    TX/RX + GND            │  (Python)    │
│  Runs miner ROM │                           │  → Node API  │
└─────────────────┘                           └──────────────┘
```

**Pros:**
- Minimal PS1 code (just attestation + serial I/O)
- PC handles TLS, JSON, networking
- Works with any PS1 model

**Cons:**
- Requires PC connection
- Slow attestation (~30-60 seconds)

### Option B: PS1 Network Adapter (ADVANCED)

```
┌─────────────────┐     Ethernet      ┌─────────────┐
│  PlayStation 1  │◄─────────────────►│  Internet   │
│  + BB Unit      │    (10 Mbps)      │  → Node     │
└─────────────────┘
```

**Pros:**
- Fully standalone
- Faster network access

**Cons:**
- Requires rare Network Adapter (SCPH-10350)
- Complex TCP/IP stack in 2 MB RAM
- Only works with PS2 BB Unit (not pure PS1)

### Option C: Parallel Station Link (EXPERIMENTAL)

```
┌─────────────────┐    Parallel Cable    ┌──────────────┐
│  PlayStation 1  │◄────────────────────►│  PC Bridge   │
│  (Parallel I/O) │     (~100 KB/s)      │  (Python)    │
└─────────────────┘                      └──────────────┘
```

**Pros:**
- Faster than serial
- No special hardware needed

**Cons:**
- Requires parallel cable (SCPH-1040)
- Complex parallel protocol

---

## Implementation Plan (Option A - Serial Bridge)

### Phase 1: Development Environment Setup

1. **Install PSn00bSDK** (modern PS1 dev toolchain)
   ```bash
   git clone https://github.com/LM-Softland/PSn00bSDK
   cd PSn00bSDK
   # Follow build instructions for your platform
   ```

2. **Install MIPS cross-compiler**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install mips-linux-gnu-gcc
   
   # Or use PSn00bSDK bundled toolchain
   ```

3. **Test with "Hello World"**
   - Compile and run on real PS1 or emulator (DuckStation)

### Phase 2: PS1 Miner Core (C Language)

**File:** `ps1_miner/main.c`

Key components:
- SHA-256 implementation (optimized for MIPS)
- Hardware fingerprint collection
- Serial communication driver
- Memory card save/load (wallet storage)

**Memory Budget:**
- Code: 512 KB
- Stack: 256 KB
- Heap: 256 KB
- Framebuffer: 512 KB
- Remaining: 512 KB for runtime

### Phase 3: PC Bridge Software

**File:** `ps1_bridge/bridge.py`

Handles:
- Serial communication with PS1
- HTTPS requests to RustChain node
- Wallet management
- Logging

### Phase 4: Hardware Fingerprint for PS1

Unique PS1 identifiers:
- **BIOS version** (different per region/model)
- **CD-ROM timing** (mechanical variance)
- **Controller port jitter**
- **RAM timing variance**
- **GPU (GTE) timing fingerprint**

### Phase 5: Testing & Validation

1. Test on DuckStation emulator
2. Test on real PS1 hardware (SCPH-1001)
3. Verify attestation with RustChain node
4. Document setup process

---

## File Structure

```
rustchain-ps1-port/
├── PS1_PORT_PLAN.md          # This document
├── ps1_miner/
│   ├── Makefile              # PSn00bSDK build config
│   ├── main.c                # Main miner loop
│   ├── sha256.c              # SHA-256 for MIPS
│   ├── sha256.h
│   ├── serial.c              # Serial I/O driver
│   ├── serial.h
│   ├── fingerprint.c         # HW fingerprint collection
│   ├── fingerprint.h
│   ├── memcard.c             # Memory card I/O
│   ├── memcard.h
│   └── linkfile              # Linker script
├── ps1_bridge/
│   ├── bridge.py             # PC bridge software
│   ├── requirements.txt
│   └── config.json
├── firmware/
│   └── rustchain_ps1_miner.bin  # Compiled binary
└── docs/
    ├── BUILD.md              # Build instructions
    ├── SETUP.md              # Hardware setup
    └── TROUBLESHOOTING.md
```

---

## Code Samples

### Serial Communication (PS1 side)

```c
// ps1_miner/serial.c
#include <psxgpu.h>
#include <psxapi.h>

#define SERIAL_BAUD 9600

void serial_init() {
    // Initialize UART
    SetRCnt(0x1000, SERIAL_BAUD, 0x1000);
    EnableEvent(0x0400);  // Serial RX event
}

int serial_send(const char* data, int len) {
    for (int i = 0; i < len; i++) {
        while (!CheckEvent(0x0400));  // Wait for TX ready
        PutC(data[i]);
    }
    return len;
}

int serial_recv(char* buf, int max_len) {
    int received = 0;
    while (received < max_len) {
        if (CheckEvent(0x0400)) {
            buf[received++] = GetC();
            if (buf[received-1] == '\n') break;
        }
    }
    buf[received] = '\0';
    return received;
}
```

### SHA-256 for MIPS

```c
// ps1_miner/sha256.c
// Optimized for MIPS R3000A (no FPU)

static const uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
    // ... rest of constants
};

#define ROTR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))
#define CH(x, y, z) (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x, y, z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))

void sha256_transform(uint32_t* state, const uint8_t* block) {
    uint32_t a, b, c, d, e, f, g, h;
    uint32_t W[64];
    
    // Unpack block (big-endian)
    for (int i = 0; i < 16; i++) {
        W[i] = ((uint32_t)block[i*4] << 24) |
               ((uint32_t)block[i*4+1] << 16) |
               ((uint32_t)block[i*4+2] << 8) |
               ((uint32_t)block[i*4+3]);
    }
    
    // Extend
    for (int i = 16; i < 64; i++) {
        uint32_t s0 = ROTR(W[i-15], 7) ^ ROTR(W[i-15], 18) ^ (W[i-15] >> 3);
        uint32_t s1 = ROTR(W[i-2], 17) ^ ROTR(W[i-2], 19) ^ (W[i-2] >> 10);
        W[i] = W[i-16] + s0 + W[i-7] + s1;
    }
    
    // Main loop (optimized for MIPS)
    a = state[0]; b = state[1]; c = state[2]; d = state[3];
    e = state[4]; f = state[5]; g = state[6]; h = state[7];
    
    for (int i = 0; i < 64; i++) {
        uint32_t S1 = ROTR(e, 6) ^ ROTR(e, 11) ^ ROTR(e, 25);
        uint32_t ch = CH(e, f, g);
        uint32_t temp1 = h + S1 + ch + K[i] + W[i];
        uint32_t S0 = ROTR(a, 2) ^ ROTR(a, 13) ^ ROTR(a, 22);
        uint32_t maj = MAJ(a, b, c);
        uint32_t temp2 = S0 + maj;
        
        h = g; g = f; f = e; e = d + temp1;
        d = c; c = b; b = a; a = temp1 + temp2;
    }
    
    state[0] += a; state[1] += b; state[2] += c; state[3] += d;
    state[4] += e; state[5] += f; state[6] += g; state[7] += h;
}
```

### PC Bridge Software

```python
# ps1_bridge/bridge.py
import serial
import requests
import json
import time

NODE_URL = "https://rustchain.org"
SERIAL_PORT = "COM3"  # or /dev/ttyUSB0
BAUD_RATE = 9600

def read_ps1_line(ser):
    """Read line from PS1 serial"""
    line = b""
    while True:
        byte = ser.read(1)
        if byte == b'\n' or byte == b'':
            break
        line += byte
    return line.decode('ascii').strip()

def write_ps1(ser, data):
    """Send data to PS1"""
    ser.write((data + '\n').encode('ascii'))

def main():
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    print(f"Connected to PS1 on {SERIAL_PORT}")
    
    wallet = load_or_create_wallet()
    print(f"Wallet: {wallet}")
    
    while True:
        # Send challenge to PS1
        nonce = generate_nonce()
        write_ps1(ser, f"CHALLENGE:{nonce}")
        
        # Wait for PS1 attestation
        response = read_ps1_line(ser)
        if response.startswith("ATTEST:"):
            attestation = json.loads(response[7:])
            
            # Submit to node
            result = submit_attestation(wallet, attestation)
            write_ps1(ser, f"RESULT:{result['status']}")
            
            print(f"Attestation: {result['status']}")
        
        time.sleep(600)  # 10 minute epochs

if __name__ == "__main__":
    main()
```

---

## Build Instructions

### Prerequisites

- Windows 10/11 or Linux
- PSn00bSDK installed
- MIPS cross-compiler
- Serial adapter (USB-to-TTL or null modem cable)

### Build Steps

```bash
# 1. Clone the repo
cd rustchain-ps1-port

# 2. Build PS1 miner
cd ps1_miner
make clean && make

# Output: rustchain_ps1_miner.bin

# 3. Build PC bridge (optional, Python)
cd ../ps1_bridge
pip install -r requirements.txt

# 4. Test with emulator
# Load rustchain_ps1_miner.bin in DuckStation
```

### Flashing to PS1

**Method 1: PS1 Link Cable**
- Use PS1 Link Cable + PSn00bSDK loader
- Upload binary directly to PS1 RAM

**Method 2: Modded PS1**
- Copy to memory card or USB drive
- Run via PS1 homebrew loader

**Method 3: Development Console (DTL-H1000/2000)**
- Use Sony debug station tools

---

## Testing Checklist

- [ ] PS1 miner compiles without errors
- [ ] SHA-256 produces correct hashes
- [ ] Serial communication works (loopback test)
- [ ] Memory card save/load works
- [ ] Hardware fingerprint collection works
- [ ] PC bridge receives attestations
- [ ] Node accepts PS1 attestations
- [ ] Rewards are distributed correctly
- [ ] Antiquity multiplier (2.8x) is applied

---

## Security Considerations

1. **Anti-emulation**: PS1 emulator timing differs from real hardware
2. **Serial binding**: Wallet bound to PS1 serial number
3. **Memory card encryption**: XOR with BIOS version
4. **Fleet detection**: PS1 miners share `retro_console` bucket (RIP-201)

---

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Phase 1: Setup | 1-2 days | Working dev environment |
| Phase 2: PS1 Core | 3-5 days | Compiling miner binary |
| Phase 3: PC Bridge | 1-2 days | Working bridge software |
| Phase 4: Fingerprint | 2-3 days | HW fingerprint implemented |
| Phase 5: Testing | 2-3 days | Tested on real hardware |
| **Total** | **9-15 days** | Production-ready PS1 miner |

---

## References

- [PSn00bSDK Documentation](https://github.com/LM-Softland/PSn00bSDK)
- [RIP-304: Retro Console Mining](https://github.com/Scottcjn/Rustchain/issues/488)
- [RIP-200: 1 CPU = 1 Vote](https://github.com/Scottcjn/Rustchain/blob/main/rips/docs/RIP-0200-round-robin-1cpu1vote.md)
- [MIPS R3000A Datasheet](https://en.wikipedia.org/wiki/MIPS_R3000)
- [PS1 Hardware Reference](https://psx-spx.consoledev.net/)

---

## Bounty Claim

**GitHub:** @48973 (subagent: 马)

**Wallet:** `RTC4325af95d26d59c3ef025963656d22af638bb96b`

**Status:** Plan created, ready for implementation

---

*"Every CPU deserves dignity" — Even a 30-year-old game console.* 🦀🎮
