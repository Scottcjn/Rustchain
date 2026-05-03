# RIP-0683: Console Mining Setup Guide

## Overview

This guide walks you through setting up a retro game console as a RustChain miner using a Raspberry Pi Pico serial bridge. Console mining enables vintage hardware from 1983-2001 to earn RTC rewards through Proof of Antiquity consensus.

**To our knowledge, this is the first blockchain to mine on vintage game console silicon.**

## Supported Consoles

| Console | CPU | Release Year | Multiplier | Status |
|---------|-----|--------------|------------|--------|
| NES/Famicom | Ricoh 2A03 (6502) | 1983 | 2.8x | ✅ Supported |
| SNES/Super Famicom | Ricoh 5A22 (65C816) | 1990 | 2.7x | ✅ Supported |
| Nintendo 64 | NEC VR4300 (MIPS) | 1996 | 2.5x | ✅ Supported |
| Game Boy | Sharp LR35902 (Z80) | 1989 | 2.6x | ✅ Supported |
| Game Boy Advance | ARM7TDMI | 2001 | 2.3x | ✅ Supported |
| Sega Genesis | Motorola 68000 | 1988 | 2.5x | ✅ Supported |
| Sega Master System | Zilog Z80 | 1986 | 2.6x | ✅ Supported |
| Sega Saturn | Hitachi SH-2 (dual) | 1994 | 2.6x | ✅ Supported |
| PlayStation 1 | MIPS R3000A | 1994 | 2.8x | ✅ Supported |

## Hardware Requirements

### Minimum Setup (~$10 USD)

1. **Retro game console** (any from the list above)
2. **Raspberry Pi Pico** ($4 USD)
   - Standard Pico for USB connection to PC
   - Pico W for standalone WiFi operation
3. **Controller port adapter** (DIY or purchase)
   - Connects Pico to console controller port
   - Schematics provided below
4. **USB cable** (USB-A to Micro-USB)
5. **PC or laptop** (for running RustChain node)

### Optional Upgrades

- **Pico W** ($6 USD) - Enables standalone WiFi mining
- **Custom PCB adapter** - More reliable than breadboard
- **Multiple consoles** - One Pico can switch between consoles

## Step 1: Build Controller Port Adapter

### NES/SNES Adapter

```
NES Controller Port (male) → Pico GPIO
───────────────────────────────────────
Pin 1 (Latch)            → GPIO 5
Pin 2 (Clock)            → GPIO 6
Pin 3 (Data)             → GPIO 7
Pin 4 (VCC)              → VBUS (5V)
Pin 5 (GND)              → GND
Pin 6 (Latch)            → GPIO 5 (parallel with Pin 1)
Pin 7 (Clock)            → GPIO 6 (parallel with Pin 2)
```

### N64 Adapter

```
N64 Controller Port (male) → Pico GPIO
────────────────────────────────────────
Pin 1 (Data)               → GPIO 2
Pin 2 (Unused)             → NC
Pin 3 (GND)                → GND
Pin 4 (VCC)                → VBUS (5V)
```

### Genesis Adapter

```
Genesis Controller Port (male) → Pico GPIO
───────────────────────────────────────────
Pin 1 (Up)                     → GPIO 0
Pin 2 (Down)                   → GPIO 1
Pin 3 (Left)                   → GPIO 2
Pin 4 (Right)                  → GPIO 3
Pin 5 (B)                      → GPIO 4
Pin 6 (C)                      → GPIO 5
Pin 7 (GND)                    → GND
Pin 8 (A)                      → GPIO 6
Pin 9 (Start)                  → GPIO 7
```

## Step 2: Flash Pico Firmware

### Prerequisites

- Raspberry Pi Pico
- USB cable
- Computer with Arduino IDE or PlatformIO

### Installation

1. **Install Arduino IDE** (if not already installed)
   ```bash
   # Ubuntu/Debian
   sudo snap install arduino
   
   # macOS
   brew install --cask arduino
   
   # Windows: Download from https://www.arduino.cc/en/software
   ```

2. **Add Pico board support**
   - Open Arduino IDE
   - Go to `File → Preferences`
   - Add to "Additional Board Manager URLs":
     ```
     https://github.com/earlephilhower/arduino-pico/releases/download/global/package_rp2040_index.json
     ```
   - Go to `Tools → Board → Boards Manager`
   - Search for "Raspberry Pi Pico"
   - Install "Raspberry Pi Pico/RP2040" by Earle Philhower

3. **Install dependencies**
   - In Arduino IDE: `Sketch → Include Library → Manage Libraries`
   - Install:
     - `SHA256` by Dominik Reichert
     - `ArduinoJson` by Benoit Blanchon

4. **Load firmware**
   - Open `miners/console/pico_bridge_firmware/pico_bridge.ino`
   - Select board: `Tools → Board → Raspberry Pi Pico → Raspberry Pi Pico`
   - Select port: `Tools → Port → /dev/ttyACM0` (Linux) or `COM3` (Windows)
   - Click Upload (→)

5. **Verify installation**
   - Open Serial Monitor (115200 baud)
   - Reset Pico
   - Should see: `PICO_READY|RIP-0683 Console Bridge v1.0|`

## Step 3: Prepare Console ROM

### N64 Attestation ROM

The console needs a custom ROM that:
1. Receives nonce from Pico
2. Computes SHA-256(nonce || wallet)
3. Outputs result via controller port

**ROM Source**: See `miners/console/n64_attestation_rom/` (future implementation)

### Alternative: Pico-Only Mode

For consoles without custom ROM capability, the Pico can:
1. Simulate controller polling
2. Measure timing characteristics
3. Compute hash on behalf of console (with reduced multiplier)

## Step 4: Configure RustChain Node

### Update Node Configuration

Edit your node's configuration file:

```python
# config.py
CONSOLE_MINING_ENABLED = True
PICO_BRIDGE_PORT = "/dev/ttyACM0"  # Linux
# PICO_BRIDGE_PORT = "COM3"  # Windows
SUPPORTED_CONSOLE_ARCHS = [
    "nes_6502", "snes_65c816", "n64_mips",
    "genesis_68000", "gameboy_z80", "ps1_mips"
]
```

### Start Node with Console Support

```bash
cd node
python3 rustchain_v2_integrated_v2.2.1_rip200.py --console-mining
```

## Step 5: Submit Attestation

### Manual Test

```bash
# Send ATTEST command to Pico
echo "ATTEST|abc123|RTC1Wallet001|$(date +%s)" > /dev/ttyACM0

# Read response
cat < /dev/ttyACM0
```

Expected response:
```
OK|PICO001|n64_mips|{"ctrl_port_cv":0.005,"rom_hash_time_us":847000,...}|<hash>
```

### Automated Mining

The node automatically:
1. Detects Pico bridge on serial port
2. Sends challenge nonce
3. Receives timing data and hash
4. Validates anti-emulation checks
5. Submits to consensus layer
6. Distributes rewards to `retro_console` bucket

## Step 6: Verify Mining Status

### Check Node Logs

```bash
tail -f node/logs/rustchain.log | grep "console"
```

Expected output:
```
[CONSOLE] Registered n64_mips miner (PICO001)
[CONSOLE] Attestation passed: CV=0.005, ROM_time=847ms
[REWARDS] retro_console bucket: 3 miners, 0.333 share
```

### Check Fleet Bucket Status

```bash
curl http://localhost:5000/api/miners/fleet_status
```

Response:
```json
{
  "buckets": {
    "retro_console": {
      "miner_count": 3,
      "share": 0.333,
      "active_archs": ["n64_mips", "nes_6502", "ps1_mips"]
    }
  }
}
```

## Troubleshooting

### Pico Not Detected

**Symptoms**: Serial port not found, no response

**Solutions**:
1. Check USB cable (some are charge-only)
2. Hold BOOTSEL button while plugging in Pico
3. Verify port: `ls /dev/ttyACM*` (Linux) or Device Manager (Windows)

### CV Too Low (Emulator Detected)

**Symptoms**: `ERROR|timing_too_uniform`

**Causes**:
- Console not powered on
- Wrong controller port wiring
- Emulator instead of real hardware

**Solutions**:
1. Verify console is running attestation ROM
2. Check controller port connections
3. Ensure real hardware, not FPGA/emulator

### ROM Hash Time Wrong

**Symptoms**: `ERROR|Suspicious hardware: ROM execution time outside tolerance`

**Causes**:
- Wrong console architecture selected
- Overclocked console
- Timing measurement bug

**Solutions**:
1. Verify correct `SET_CONSOLE` command sent to Pico
2. Check console is stock (not overclocked)
3. Increase tolerance in firmware (±15% → ±20%)

### Fleet Detection Triggered

**Symptoms**: Reduced rewards, `fleet_score > 0.5`

**Causes**:
- Multiple consoles on same IP/subnet
- Correlated attestation timing
- Similar fingerprint profiles

**Solutions**:
1. Spread consoles across different networks
2. Add random delay to attestation timing
3. Each console should have unique Pico ID

## Economics

### Expected Rewards

Console miners share the `retro_console` bucket equally with other console miners.

**Example** (assuming 10 total miners, 3 in retro_console):
- Total block reward: 1.5 RTC
- retro_console bucket share: 1.5 / 3 = 0.5 RTC
- Your console share: 0.5 / (number of console miners)

**With 2.5x multiplier** (N64):
- Base reward × 2.5 = higher share within bucket

### ROI Calculation

**Initial Investment**:
- Console: $20-50 (eBay)
- Pico: $4
- Adapter: $5 (parts)
- **Total**: ~$30-60

**Annual Revenue** (estimated):
- 0.1-0.5 RTC/day × 365 days × $0.50/RTC = **$18-91/year**

**Payback Period**: 4-36 months

**Note**: Rewards depend on network participation, RTC price, and console bucket size.

## Advanced Topics

### Multi-Console Bridge

One Pico can manage multiple consoles:
- Use GPIO multiplexer
- Switch controller port connections
- Each console gets unique miner ID

### Pico W Standalone Mode

Pico W can operate without PC:
- Connects to WiFi
- Sends attestations directly to node
- Requires custom firmware build

### Custom ROM Development

Develop attestation ROMs for additional consoles:
- Use existing dev tools (gcc6502, mips64-elf-gcc)
- Link against librustchain (SHA-256 implementation)
- Output ROM format (.nes, .z64, .bin)

## Security Considerations

### Anti-Spoof Measures

1. **Pico board ID** - Unique OTP ROM (cannot reprogram)
2. **Timing profiles** - Real hardware has characteristic jitter
3. **ROM execution time** - Must match known CPU performance
4. **Fleet detection** - IP clustering, timing correlation

### Known Limitations

- FPGA consoles may pass timing checks (under research)
- High-end emulators + fake bridge possible (mitigated by fleet detection)
- Console farms limited by bucket normalization

## Future Work

### Phase 2 (Q2 2026)
- Additional consoles: Atari 2600, Neo Geo, Dreamcast
- Pico W standalone firmware
- Multi-console bridge support

### Phase 3 (Q3 2026)
- Hardware anchor on Ergo
- On-chain attestation registry
- Console-specific NFT badges

## References

- [RIP-0683 Specification](../rips/docs/RIP-0683-console-bridge-integration.md)
- [RIP-0304: Retro Console Mining](../rips/docs/RIP-0304-retro-console-mining.md)
- [RIP-201: Fleet Immune System](../rips/docs/RIP-0201-fleet-immune-system.md)
- [Legend of Elya](https://github.com/ilya-kh/legend-of-elya) - N64 neural network demo
- [Pico SDK Documentation](https://datasheets.raspberrypi.com/pico/getting-started-with-pico.pdf)

## Support

- **GitHub Issues**: https://github.com/Scottcjn/Rustchain/issues
- **Discord**: https://discord.gg/rustchain
- **Documentation**: https://rustchain.org/docs

---

© 2026 RustChain Core Team - Apache License 2.0
