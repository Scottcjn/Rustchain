# Pico Serial Bridge Miner

RIP-304 compliant miner for retro console mining via Raspberry Pi Pico serial bridge.

## Overview

This miner client communicates with a Raspberry Pi Pico (RP2040) microcontroller that serves as a serial-to-controller bridge for retro game consoles. The Pico captures timing data from console controller ports and relays attestation payloads to the RustChain network.

**Supported Consoles:**
- NES/Famicom (Ricoh 2A03, 6502 derivative)
- SNES/Super Famicom (Ricoh 5A22, 65C816)
- Nintendo 64 (NEC VR4300, MIPS R4300i)
- Sega Genesis/Mega Drive (Motorola 68000)
- Sega Master System (Zilog Z80)
- Sega Saturn (Hitachi SH-2)
- PlayStation 1 (MIPS R3000A)
- Game Boy / Game Boy Color (Sharp LR35902, Z80 derivative)
- Game Boy Advance (ARM7TDMI)

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Retro Console  │────▶│  Raspberry Pi    │────▶│  PC / SBC       │
│  (attestation   │Ctrl │  Pico (RP2040)   │USB  │  (miner client) │
│   ROM in cart)  │Port │  Serial Bridge   │Serial│  (this software)│
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                              ┌─────────────────┐
                                              │  RustChain Node │
                                              │  /attest/submit │
                                              └─────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.8+
- Raspberry Pi Pico (standard or Pico W variant)
- USB cable (micro-USB for Pico, USB-C for Pico W)
- Console-specific controller port adapter (see wiring diagrams below)

### Installation

```bash
pip install -r requirements.txt
```

### Configuration

Copy `config.example.json` to `config.json` and edit:

```json
{
  "wallet_id": "RTC<your_wallet_address>",
  "node_url": "https://rustchain.org",
  "miner_name": "n64-scott-unit1",
  "console_type": "n64_mips",
  "pico_port": "/dev/ttyACM0",
  "pico_baud": 115200,
  "simulation_mode": false
}
```

### Running the Miner

```bash
# Normal mode (requires Pico connected)
python pico_bridge_miner.py

# Simulation mode (no hardware required, for testing)
python pico_bridge_miner.py --simulate

# Headless mode (no GUI)
python pico_bridge_miner.py --headless --wallet RTC<address> --node https://rustchain.org
```

## Simulation Mode

For development and testing without physical hardware, enable simulation mode:

```bash
python pico_bridge_miner.py --simulate --wallet RTC<address>
```

This generates realistic mock timing data that mimics real console hardware characteristics.

## Wiring Diagrams

### NES Controller Port to Pico

```
NES Controller Port (male, looking at console)
  ┌─────────────┐
  │ 1 2 3 4 5 6 │
  └─────────────┘
  Pin 1: VCC (5V)  ──────▶ Pico VBUS
  Pin 2: Data  ──────────▶ Pico GPIO 0 (with 3.3V level shifter)
  Pin 3: Latch ──────────▶ Pico GPIO 1 (with level shifter)
  Pin 4: Clock ──────────▶ Pico GPIO 2 (with level shifter)
  Pin 5: NC
  Pin 6: GND  ───────────▶ Pico GND
```

### N64 Controller Port to Pico

```
N64 Controller Port (female, looking at cable)
  ┌───────────────┐
  │ 1  2  3  4    │
  │ 5  6  7       │
  └───────────────┘
  Pin 1: VCC (3.3V) ─────▶ Pico VBUS
  Pin 2: Data (bidir) ───▶ Pico GPIO 0 (3.3V tolerant)
  Pin 3: NC
  Pin 4: GND ────────────▶ Pico GND
```

**Note:** N64 uses 3.3V logic - no level shifter needed!

## Pico Firmware

The Pico requires custom firmware to capture controller port timing. See the separate repository:
- `rustchain-pico-firmware` (coming soon)

### Firmware Features

- PIO state machine for precise timing capture (125 MHz sampling)
- USB CDC-ACM serial interface
- Challenge-response protocol for attestation
- Unique RP2040 board ID inclusion in payloads

## Attestation Payload

Example payload sent to RustChain node:

```json
{
  "miner": "n64-scott-unit1",
  "miner_id": "n64-pico-bridge-001",
  "nonce": "<from_challenge>",
  "report": {
    "nonce": "<from_challenge>",
    "commitment": "<sha256_computed_by_console>",
    "derived": {
      "ctrl_port_timing_mean_ns": 250000,
      "ctrl_port_timing_stdev_ns": 1250,
      "ctrl_port_cv": 0.005,
      "rom_hash_result": "<sha256_from_console>",
      "rom_hash_time_us": 847000,
      "bus_jitter_samples": 500
    },
    "entropy_score": 0.075
  },
  "device": {
    "family": "console",
    "arch": "n64_mips",
    "model": "Nintendo 64 NUS-001",
    "cpu": "NEC VR4300 (MIPS R4300i) 93.75MHz",
    "cores": 1,
    "memory_mb": 4,
    "bridge_type": "pico_serial",
    "bridge_firmware": "1.0.0"
  },
  "signals": {
    "pico_serial": "<RP2040_unique_board_ID>",
    "ctrl_port_protocol": "joybus",
    "rom_id": "rustchain_attest_n64_v1"
  },
  "fingerprint": {
    "all_passed": true,
    "bridge_type": "pico_serial",
    "checks": {
      "ctrl_port_timing": {"passed": true, "data": {"cv": 0.005, "samples": 500}},
      "rom_execution_timing": {"passed": true, "data": {"hash_time_us": 847000}},
      "bus_jitter": {"passed": true, "data": {"jitter_stdev_ns": 1250}},
      "anti_emulation": {"passed": true, "data": {"emulator_indicators": []}}
    }
  }
}
```

## Troubleshooting

### Pico Not Detected

```bash
# List USB serial devices
ls /dev/ttyACM*  # Linux
ls /dev/cu.usbmodem*  # macOS

# Check dmesg for Pico enumeration
dmesg | grep -i pico
```

### Permission Denied (Linux)

```bash
sudo usermod -a -G dialout $USER
# Log out and back in
```

### Timing CV Too Low (Emulation Flag)

If `ctrl_port_cv < 0.0001`, the server will flag emulation. Ensure:
- Real console hardware is being used
- Controller port connection is stable
- Pico firmware is capturing at full 125 MHz PIO clock

## Security Notes

- Each RP2040 has a unique board ID burned into OTP ROM
- Challenge-response prevents replay attacks
- Controller port timing jitter is physically impossible to emulate perfectly
- Fleet detection applies to console farms (RIP-201)

## References

- RIP-304: `/rips/docs/RIP-0304-retro-console-mining.md`
- Legend of Elya N64: https://github.com/sophiaeagent-beep/n64llm-legend-of-Elya
- RP2040 Datasheet: https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf
