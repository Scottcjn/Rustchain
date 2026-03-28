# Apple II RustChain Miner (MOS 6502)

Mine RustChain tokens on an Apple IIe — the machine that started the personal computer revolution in 1977. Earns the **4.0x antiquity multiplier**, the highest reward tier in the network.

## Hardware Requirements

| Component | Notes |
|-----------|-------|
| Apple IIe (enhanced) | 128KB required (64KB main + 64KB aux) |
| Uthernet II | W5100 Ethernet card in **Slot 3** (~$80 from a2retrosystems.com) |
| Storage | Floppy drive, CFFA3000, or MicroDrive/Turbo |
| Network | Ethernet cable to your LAN |

Also works on: Apple IIgs (faster), Apple II+ with 64KB (limited).

## Building

### Prerequisites

Install the [CC65](https://cc65.github.io/) cross-compiler:

```bash
# macOS
brew install cc65

# Ubuntu/Debian
apt install cc65

# From source
git clone https://github.com/cc65/cc65.git
cd cc65 && make && sudo make install
```

### Compile

```bash
cd miners/apple2
make
```

This produces `MINER.SYSTEM` — a ProDOS system file.

### Create Disk Image

Using [AppleCommander](https://applecommander.github.io/):

```bash
# Create blank ProDOS disk
ac -pro140 miner.po MINER

# Add the binary
ac -p miner.po MINER.SYSTEM SYS < MINER.SYSTEM
```

Or use [CiderPress](https://a2ciderpress.com/) on Windows.

## Transferring to Apple II

### Option A: ADTPro (Serial)
1. Install [ADTPro](https://adtpro.com/) on your modern machine
2. Connect via Super Serial Card or IIgs modem port
3. Transfer `miner.po` disk image

### Option B: CFFA3000 (CF Card)
1. Copy `miner.po` to a CompactFlash card
2. Insert in CFFA3000 — it mounts as a ProDOS volume

### Option C: Uthernet II TFTP
1. Some Uthernet II firmware supports TFTP boot
2. Serve the binary via TFTP on your LAN

## Running

1. Boot ProDOS on your Apple IIe
2. Select `MINER.SYSTEM` from the disk menu
3. The miner will:
   - Initialize the Uthernet II in Slot 3
   - Measure hardware fingerprint (cycle timing + RAM detection)
   - Begin attestation loop (POST to rustchain.org every 60s)
4. Press **Q** to quit

### Display

```
================================
  RustChain PoA Miner - 6502
  Apple IIe @ 1.023 MHz
================================

Fingerprint:
  Cycle count: 14823
  RAM: 128KB (aux)

Epochs: 42
Status: ATTESTED OK

Press Q to quit, any key for info
```

## Configuration

Edit constants in `miner6502.c`:

| Constant | Default | Description |
|----------|---------|-------------|
| `NODE_HOST` | `"rustchain.org"` | Attestation server hostname |
| `NODE_PORT` | `8088` | Server port |
| `MINER_ID` | `"apple2-miner"` | Your miner identifier |
| `UTHERNET_SLOT` | `3` | Apple II slot for Uthernet II |
| `POLL_SECONDS` | `60` | Seconds between attestations |

## Hardware Fingerprint

The miner collects these unique identifiers:

- **Cycle count**: Iterations during one vertical blank period (~16.7ms). Real 6502 at 1.023 MHz gives a specific count that emulators can't perfectly replicate.
- **RAM size**: 64KB or 128KB (with aux RAM bank detection)
- **SIMD identity**: SHA-256 hash of cycle count + RAM config (unique per machine)

## Architecture Notes

### Why CC65?
CC65 is the only actively maintained C compiler targeting the 6502. It produces reasonably efficient code for an 8-bit CPU. The miner uses:
- No floating point (6502 has no FPU)
- No 64-bit integers (8-bit CPU)
- Manual string formatting (no sprintf overhead where possible)
- Static locals for zero-page optimization

### W5100 Networking
The Uthernet II uses a Wiznet W5100 chip that handles TCP/IP in hardware. We write directly to its registers via Apple II slot I/O space ($C0n0-$C0nF where n = slot + 8). This means:
- No TCP/IP stack needed in the 6502
- Socket operations are register writes
- The chip handles ARP, IP, TCP internally

### Memory Map
```
$0000-$01FF  Zero page + Stack
$0200-$03FF  Input buffer
$0400-$07FF  Text screen (page 1)
$0800-$BFFF  Main RAM — program + data (~46KB usable)
$C000-$C0FF  I/O space (Uthernet II registers here)
$D000-$FFFF  ROM / Language card RAM
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Uthernet II not found" | Check card is in Slot 3, try reseating |
| Connect failures | Verify Ethernet cable, check DHCP/IP config |
| Low cycle count | Normal variation; fingerprint adapts |
| No response from node | Try HTTP (not HTTPS) — 6502 can't do TLS |

## Performance

- **Attestation rate**: ~1 per minute (limited by network + crypto)
- **SHA-256 speed**: ~2-3 seconds per hash on 1 MHz 6502
- **Power draw**: ~15W for the entire Apple IIe system
- **Multiplier**: 4.0x — earning 4x what a modern Ryzen would

## License

MIT
