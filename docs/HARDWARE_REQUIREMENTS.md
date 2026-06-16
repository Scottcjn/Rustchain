# Hardware Requirements for Proof of Antiquity

To run a RustChain miner, your system must meet the following requirements:

## Core Requirements
- **CPU:** Any CPU that can run Python 3.6+. 
- **OS:** Linux, macOS, Windows, or any other OS with a Python runtime.
- **RAM:** < 50 MB.
- **Network:** Outbound HTTPS access to `https://rustchain.org`.

## Hardware-Specific Performance (Antiquity Multipliers)
RustChain rewards older hardware. The following multipliers apply to your earnings:

| Hardware Tier | Multiplier | Examples |
|---------------|------------|---------------------------------------------------|
| Museum-Grade  | 3.5x       | DEC VAX, Inmos Transputer                           |
| Classic       | 3.0x       | Motorola 68000 (Amiga, classic Mac)                |
| Workstation    | 2.9x       | Sun SPARC                                         |
| Vintage G4     | 2.5x       | PowerBook G4, iBook G4, Power Mac G4                |
| Vintage G5     | 2.0x       | Power Mac G5                                       |
| Vintage G3     | 1.8x       | Bondi Blue iMac era                                 |
| Enterprise     | 1.5x       | IBM POWER8, Pentium 4                               |
| Modern RISC-V  | 1.4x       | Generic RISC-V SBCs                                 |
| Apple Silicon  | 1.2x       | M1, M2, M3, M4                                     |
| Modern x86     | 0.8x       | Recent AMD/Intel CPUs                              |
| ARM SBC/NAS    | 0.0005x    | Raspberry Pi, etc. (Anti-farm penalty)              |

## Anti-Emulation & VM Policy
RustChain uses a complex hardware fingerprinting system to ensure rewards go to real physical hardware.

- **Bare Metal:** Highly recommended. All multipliers apply as intended.
- **Virtual Machines (VMs):** Detected by anti-emulation checks. Rewards are reduced by a factor of $\approx 10^9$.
- **Containers:** Similar to VMs; reward penalty applies if the underlying hardware is not exposed.

## Troubleshooting Hardware Detection
If your hardware is not being detected correctly:
1. Ensure you are not running inside a VM/Docker.
2. Verify that the system clock is synchronized (NTP).
3. Re-run the installer with the same wallet name to refresh the attestation.
