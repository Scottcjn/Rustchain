# RustChain i386 Miner

A bare-metal RustChain Proof-of-Antiquity miner for Intel 80386 hardware.
Written in pure C89 — no floating-point, no 64-bit types, no dynamic libraries.
Targets FreeDOS (DJGPP) or a minimal static Linux binary.

---

## Overview

The i386 miner collects a hardware fingerprint from the local machine and
periodically submits an attestation POST to a RustChain node.  No proof-of-work
computation is required; the scarcity signal comes from the verified age and
uniqueness of the hardware itself.

### Architecture constraints

| Property       | Value                                 |
|----------------|---------------------------------------|
| CPU            | Intel 80386 (16–40 MHz)               |
| RAM            | 4 MB (minimum; 8 MB recommended)      |
| FPU            | **None** — 387 co-processor optional  |
| OS (DOS)       | FreeDOS 1.3+ with DJGPP runtime       |
| OS (Linux)     | Any kernel ≥ 2.4, i386 statically linked |
| Network (DOS)  | NE2000-compatible ISA NIC             |
| Network (Linux)| Any kernel-supported Ethernet/Wi-Fi   |

---

## Hardware Requirements

### Minimum Bill of Materials (FreeDOS path)

- Intel 80386 SX or DX (any speed)
- 4 MB RAM (ISA DRAM or SIMM modules)
- ISA bus with at least one free 16-bit slot
- NE2000-compatible ISA NIC (NE2000, Realtek 8019, 3Com 3c509, etc.)
- Floppy or CF-to-IDE adapter for booting
- PC-compatible BIOS (Award, AMI, Phoenix)

### Recommended

- 8–16 MB RAM (leaves headroom for packet driver + DJGPP heap)
- 387 FPU coprocessor (the miner doesn't use it, but other software might)
- VGA/EGA display for debugging; headless is fine once confirmed working

---

## Building

### Prerequisites

#### Linux target (cross-compile on a modern host)

```bash
# Debian/Ubuntu
sudo apt-get install gcc-i686-linux-gnu binutils-i686-linux-gnu

# Fedora/RHEL
sudo dnf install gcc-i686-linux-gnu
```

Then build:

```bash
cd miners/i386
make linux
# Produces: miner386  (static ELF, runs on i386 Linux)
```

#### FreeDOS / DJGPP target

1. Install the DJGPP cross-compiler on your Linux host.
   The easiest way is the Andrew Wu DJGPP cross-compiler toolchain:

   ```bash
   # Example using a pre-built binary package
   wget https://github.com/andrewwutw/build-djgpp/releases/download/v3.4/djgpp-linux64-gcc1220.tar.bz2
   tar xf djgpp-linux64-gcc1220.tar.bz2 -C /opt/djgpp
   export PATH=/opt/djgpp/bin:$PATH
   ```

2. Build and install Watt-32 (TCP/IP stack for DOS):

   ```bash
   git clone https://github.com/gvanem/Watt-32.git
   cd Watt-32
   # Follow Watt-32 build instructions for DJGPP
   export WATT_ROOT=$(pwd)
   ```

3. Build the miner:

   ```bash
   cd miners/i386
   make dos WATT_ROOT=/path/to/Watt-32
   # Produces: miner386.exe  (DOS 32-bit protected mode)
   ```

### Syntax check (no cross-compiler needed)

```bash
make check   # runs host gcc in -fsyntax-only mode
```

---

## Network Setup

### FreeDOS — Packet Driver

The DJGPP/Watt-32 stack uses a **packet driver** to talk to the NIC.
The packet driver lives in DOS memory and is loaded before the miner.

1. Obtain the correct packet driver for your NIC:
   - NE2000: `ne2000.com` (Crynwr packet drivers, freely available)
   - 3Com 3c509: `3c509.com`
   - Realtek 8019: `ne2000.com` (NE2000-compatible mode)

2. Boot FreeDOS and load the packet driver in `AUTOEXEC.BAT`:

   ```
   LH NE2000 0x60 10 0x300
   ```
   *(interrupt 0x60, IRQ 10, I/O base 0x300 — adjust for your NIC)*

3. Set Watt-32 configuration in `WATTCP.CFG`:

   ```
   my_ip    = 192.168.1.50
   netmask  = 255.255.255.0
   gateway  = 192.168.1.1
   nameserv = 8.8.8.8
   ```

4. Run the miner:

   ```
   miner386.exe --node http://rustchain.org:8088 --id my386-dos
   ```

### Linux (i386 static binary)

Standard network configuration applies (DHCP, static IP, etc.).
No special setup beyond having a working network interface.

```bash
./miner386 --node http://rustchain.org:8088 --id my386-linux
```

---

## Usage

```
miner386 [--node <url>] [--id <miner_id>]

Options:
  --node <url>     RustChain node URL (default: http://rustchain.org:8088)
  --id   <id>      Miner identifier string (default: i386-miner)
```

### Examples

```bash
# Linux, connecting to local testnet node
./miner386 --node http://192.168.1.100:8088 --id my-vintage-386

# DOS (DJGPP)
miner386.exe --node http://rustchain.org:8088 --id freedos-386
```

---

## Hardware Fingerprint

Each attestation cycle collects:

| Field           | Source                                              |
|-----------------|-----------------------------------------------------|
| `cpu_vendor`    | CPUID leaf 0 (486+) or `"i386-NoCPUID"` on 386     |
| `has_cpuid`     | EFLAGS.ID toggle test                               |
| `cpu_flags`     | Raw EFLAGS register                                 |
| `ram_kb`        | BIOS 0x413 (DOS) or `/proc/meminfo` (Linux)         |
| `clock_ticks`   | Timing loop iterations per ~100 ms                  |
| `hw_fingerprint`| SHA-256 of the above fields (hex string)            |
| `timestamp`     | Unix time via `time()`                              |

These are POSTed as JSON to `<node>/attest/submit`.

### Example payload

```json
{
  "miner_id": "my386",
  "arch": "i386",
  "cpu_vendor": "i386-NoCPUID",
  "has_cpuid": 0,
  "cpuid_max_leaf": 0,
  "cpu_flags": 18446744073709518338,
  "ram_kb": 4096,
  "clock_ticks": 182034,
  "hw_fingerprint": "a3f1...d9e2",
  "timestamp": 1743187200
}
```

---

## Source Files

| File             | Description                                          |
|------------------|------------------------------------------------------|
| `miner386.c`     | Main miner: fingerprint, JSON build, HTTP POST loop  |
| `sha256.h`       | Self-contained SHA-256 (C89, uint32_t only)          |
| `http_client.h`  | Minimal HTTP/1.0 POST client (BSD sockets / Watt-32) |
| `Makefile`       | Build rules for Linux and DJGPP targets              |

---

## Troubleshooting

**`gethostbyname` fails on FreeDOS**
: Ensure `WATTCP.CFG` is in the current directory and `nameserv` is set.

**Binary too large for DOS**
: Use UPX to compress: `upx --best miner386.exe` (reduces by ~50 %).

**Clock ticks vary wildly**
: Normal on real hardware — interrupt latency and bus arbitration cause jitter.
  The server accepts a range.

**`i386-linux-gnu-gcc` not found**
: On Ubuntu 22.04+, the package is `gcc-i686-linux-gnu` and the binary is
  `i686-linux-gnu-gcc`. Update the `CC_LINUX` variable in the Makefile.

---

## Bounty

This implementation targets **Bounty #435 — Port RustChain Miner to Intel 386**
(150 RTC reward). See `docs/DEVELOPER_TRACTION_Q1_2026.md` for claim procedure.

---

## License

Same as the RustChain repository root. See `LICENSE`.
