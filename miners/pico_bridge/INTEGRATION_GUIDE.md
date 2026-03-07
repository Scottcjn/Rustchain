# Pico Serial Bridge Integration Guide

## Overview

This guide explains how to integrate Raspberry Pi Pico as a serial-to-controller bridge for retro console mining on RustChain (RIP-304).

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         RETRO CONSOLE MINING SYSTEM                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐      ┌──────────────────┐      ┌──────────────────┐   │
│  │ Retro Console│      │  Raspberry Pi    │      │  PC / SBC        │   │
│  │              │      │  Pico (RP2040)   │      │  Miner Client    │   │
│  │ - NES/SNES   │─────▶│  Serial Bridge   │─────▶│  (Python)        │   │
│  │ - N64/Genesis│ Ctrl │  - PIO State     │ USB  │  - Attestation   │   │
│  │ - GB/GBC/GBA │ Port │    Machine       │Serial│  - Submission    │   │
│  │ - Saturn/PS1 │      │  - 125MHz Sample │      │                  │   │
│  └──────────────┘      └──────────────────┘      └────────┬─────────┘   │
│                                                           │              │
│                                                           ▼              │
│                                                 ┌──────────────────┐    │
│                                                 │  RustChain Node  │    │
│                                                 │  - Validation    │    │
│                                                 │  - Rewards       │    │
│                                                 └──────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Supported Consoles

| Console | CPU | Year | Multiplier | Protocol |
|---------|-----|------|------------|----------|
| NES/Famicom | Ricoh 2A03 (6502) | 1983 | 2.8x | Serial shift register |
| SNES/Super Famicom | Ricoh 5A22 (65C816) | 1990 | 2.7x | Serial |
| Game Boy | Sharp LR35902 (Z80) | 1989 | 2.6x | Serial link cable |
| Game Boy Color | Sharp LR35902 @ 8MHz | 1998 | 2.5x | Serial link cable |
| Sega Master System | Zilog Z80 | 1986 | 2.6x | Parallel |
| Sega Genesis | Motorola 68000 | 1988 | 2.5x | Parallel |
| Nintendo 64 | NEC VR4300 (MIPS) | 1996 | 2.5x | Joybus (4 Mbit/s) |
| Sega Saturn | Hitachi SH-2 (dual) | 1994 | 2.6x | SMPC parallel |
| PlayStation 1 | MIPS R3000A | 1994 | 2.8x | SPI serial |
| Game Boy Advance | ARM7TDMI | 2001 | 2.3x | Serial link cable |

## Hardware Requirements

### Raspberry Pi Pico

- **RP2040 microcontroller** ($4 USD)
- **Pico** (standard) or **Pico W** (with WiFi for standalone mode)
- **Micro-USB cable** (or USB-C for Pico W)
- **Header pins** (soldered or socket)

### Console Adapter

Each console requires a custom adapter to connect its controller port to the Pico's GPIO pins. See wiring diagrams below.

### Level Shifting

- **5V consoles** (NES, SNES, Genesis): Require 5V→3.3V level shifters
- **3.3V consoles** (N64, GBA, PS1): Direct connection possible

## Wiring Diagrams

### NES Controller Port

```
NES Controller Port (male, looking at console)
  ┌─────────────┐
  │ 1 2 3 4 5 6 │
  └─────────────┘

Pin 1: VCC (5V)  ──────┬─────▶ Pico VBUS
                       │
Pin 2: Data  ──────────┼───▶ [Level Shifter] ──▶ Pico GPIO 0
                       │
Pin 3: Latch ──────────┼───▶ [Level Shifter] ──▶ Pico GPIO 1
                       │
Pin 4: Clock ──────────┼───▶ [Level Shifter] ──▶ Pico GPIO 2
                       │
Pin 5: NC              │
                       │
Pin 6: GND  ───────────┴─────▶ Pico GND
```

### N64 Controller Port

```
N64 Controller Port (female, looking at cable)
  ┌───────────────┐
  │ 1  2  3  4    │
  │ 5  6  7       │
  └───────────────┘

Pin 1: VCC (3.3V) ─────▶ Pico VBUS (or 3.3V out)
Pin 2: Data (bidir) ───▶ Pico GPIO 0 (direct, 3.3V tolerant)
Pin 3: NC
Pin 4: GND ────────────▶ Pico GND
```

**Note:** N64 uses 3.3V logic - no level shifter needed!

### SNES Controller Port

Same as NES (6-pin DIN), but uses 16-bit serial instead of 8-bit.

### Game Boy Link Port

```
Game Boy Link Port (3.5mm stereo jack)
  Tip:   VCC (3.3V) ──▶ Pico VBUS
  Ring:  Data ────────▶ Pico GPIO 0 (with level shifter)
  Sleeve: GND ────────▶ Pico GND
```

## Software Setup

### On PC/SBC (Miner Client)

```bash
cd miners/pico_bridge
pip install -r requirements.txt

# Create config
cp config.example.json config.json
# Edit config.json with your wallet and console type

# Run in simulation mode (testing)
python pico_bridge_miner.py --simulate --wallet RTC<address>

# Run with real hardware
python pico_bridge_miner.py --wallet RTC<address>
```

### Configuration Options

```json
{
  "wallet_id": "RTC<your_wallet_address>",
  "node_url": "https://rustchain.org",
  "miner_name": "n64-scott-unit1",
  "console_type": "n64_mips",
  "pico_port": "/dev/ttyACM0",
  "pico_baud": 115200,
  "simulation_mode": false,
  "attestation_interval_sec": 300
}
```

## Pico Firmware

The Pico requires custom firmware to capture controller port timing at hardware speed.

### Firmware Features

- **PIO State Machine**: Captures timing at 125 MHz (8ns resolution)
- **USB CDC-ACM**: Serial communication with PC
- **Challenge-Response**: Processes nonces from miner client
- **Board ID**: Includes unique RP2040 OTP ROM ID

### Firmware Protocol

Communication between PC and Pico uses simple text protocol:

```
PC → Pico:  ID
Pico → PC:  ID:RP2040-XXXXXXXXXXXX

PC → Pico:  CHALLENGE:<nonce>
Pico → PC:  ATTEST:{<json_payload>}
```

### Building Firmware

Firmware source code is in a separate repository:
`github.com/Scottcjn/rustchain-pico-firmware`

```bash
# Requires Raspberry Pi Pico SDK
mkdir build && cd build
cmake ..
make
# Copy pico_bridge.uf2 to Pico (hold BOOTSEL while plugging in)
```

## Attestation Flow

1. **Miner client** fetches challenge nonce from RustChain node
2. **Miner client** sends nonce to Pico via USB serial
3. **Pico** forwards nonce to console via controller port
4. **Console** runs attestation ROM, computes SHA-256(nonce || wallet)
5. **Pico** captures timing of controller port communication
6. **Pico** sends timing data + hash result back to miner client
7. **Miner client** builds attestation payload, submits to node
8. **Node** validates fingerprint, distributes rewards

## Anti-Emulation Measures

RIP-304 includes multiple anti-emulation checks:

| Check | Threshold | Purpose |
|-------|-----------|---------|
| Controller Port Timing CV | > 0.0001 | Real hardware has jitter |
| ROM Execution Time | 100ms - 10s | Matches console CPU speed |
| Bus Jitter Stdev | > 100ns | Real bus contention |
| Emulator Indicators | None | No VM/hypervisor flags |

### Why Emulators Fail

Software emulators (Project64, SNES9x, FCEUX, etc.) exhibit:

1. **Zero controller port jitter** - Perfect software timing loops
2. **Quantized execution timing** - Modern CPU clock granularity
3. **Uniform thermal response** - No physical silicon effects
4. **Perfect bus timing** - No DMA contention artifacts

The Pico's PIO state machines sample at 125 MHz - fast enough to detect these artifacts.

## Security Considerations

### Replay Attack Prevention

- **Challenge-response protocol**: Each attestation requires fresh nonce
- **Console-computed hash**: ROM computes SHA-256 using console CPU
- **Pico cannot precompute**: Doesn't know nonce in advance

### Pico Spoofing Prevention

- **Unique board ID**: RP2040 OTP ROM cannot be reprogrammed
- **Server tracks Pico IDs**: Like MAC addresses
- **Timing must match**: ROM execution time must match claimed console

### Console Farm Mitigation

- **Fleet bucket**: All consoles share `retro_console` bucket (RIP-201)
- **Equal bucket split**: 100 NES units share same pot as 1 N64
- **IP clustering detection**: Fleet immune system applies

## Troubleshooting

### Pico Not Detected

```bash
# Linux
ls /dev/ttyACM*
dmesg | grep -i pico

# macOS
ls /dev/cu.usbmodem*

# Windows
# Check Device Manager → Ports (COM & LPT)
```

### Permission Denied (Linux)

```bash
sudo usermod -a -G dialout $USER
# Log out and back in
```

### Timing CV Too Low

If `ctrl_port_cv < 0.0001`, server flags emulation:

- Ensure real console hardware (not emulator)
- Check controller port connection stability
- Verify Pico firmware captures at full 125 MHz

### ROM Hash Timeout

If ROM hash takes too long:

- Check console power and reset
- Verify attestation ROM is properly loaded
- Increase timeout in miner client config

## Testing Without Hardware

Use simulation mode for development:

```bash
python pico_bridge_miner.py --simulate --wallet RTC<address> --console n64_mips
```

This generates realistic mock timing data that passes validation.

## References

- **RIP-304**: `/rips/docs/RIP-0304-retro-console-mining.md`
- **Legend of Elya**: https://github.com/sophiaeagent-beep/n64llm-legend-of-Elya
- **RP2040 Datasheet**: https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf
- **RIP-201**: Fleet Detection Immune System

## Future Extensions

### Phase 2: Additional Consoles

- Atari 2600 (6507 CPU)
- Atari 7800 (Sally CPU)
- Neo Geo (68000)
- TurboGrafx-16 (HuC6280)
- Dreamcast (SH-4 via Maple Bus)
- GameCube (IBM Gekko PPC)

### Phase 3: Pico W Standalone

Pico W variant includes WiFi for standalone operation - no PC required.

### Phase 4: Multi-Console Bridge

Single Pico with multiple controller ports for mining on several consoles.
