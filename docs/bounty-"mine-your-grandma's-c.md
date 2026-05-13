# Vintage Miner Setup Guide: Mining RustChain on Legacy Hardware

## Overview

This guide provides step-by-step instructions to set up a RustChain mining node on vintage hardware. RustChain's DePIN (Decentralized Physical Infrastructure Network) protocol is designed to leverage older machines through AI-augmented Proof of Real Machines (PoRM). The mining process validates machine authenticity and contributes to network resilience without requiring high computational power.

**Target Hardware:**
- Core 2 Duo era Windows laptop (e.g., Dell Latitude D630, ThinkPad T61)
- PowerPC Mac (G3/G4/G5, e.g., iMac G4, Power Mac G5)
- Old Linux desktop (e.g., Pentium 4, Athlon XP)

**Prerequisites:**
- Internet connection (wired recommended for stability)
- Minimum 512 MB RAM (1 GB recommended)
- 200 MB free disk space
- Operating system: Windows XP/Vista/7, macOS 10.4+, or Linux kernel 2.6+

## Step 1: Download RustChain Client

The RustChain client is a lightweight Rust binary compiled for legacy architectures. Download the appropriate version for your system:

| Architecture | Download Link |
|--------------|---------------|
| Windows x86 (32-bit) | `https://github.com/Scottcjn/Rustchain/releases/latest/download/rustchain-win32.exe` |
| Windows x64 (64-bit) | `https://github.com/Scottcjn/Rustchain/releases/latest/download/rustchain-win64.exe` |
| macOS PowerPC | `https://github.com/Scottcjn/Rustchain/releases/latest/download/rustchain-mac-ppc` |
| macOS Intel | `https://github.com/Scottcjn/Rustchain/releases/latest/download/rustchain-mac-intel` |
| Linux x86 (32-bit) | `https://github.com/Scottcjn/Rustchain/releases/latest/download/rustchain-linux-x86` |
| Linux x64 (64-bit) | `https://github.com/Scottcjn/Rustchain/releases/latest/download/rustchain-linux-x64` |

**Note:** PowerPC Macs require macOS 10.4 (Tiger) or later. For older Linux systems, ensure `glibc` version 2.12 or newer is installed.

## Step 2: Install and Configure

### Windows (Core 2 Duo Era Laptop)

1. Download `rustchain-win32.exe` (or `rustchain-win64.exe` for 64-bit systems).
2. Run the installer as Administrator:
   ```
   rustchain-win32.exe --install
   ```
3. Create a configuration file `rustchain.conf` in the installation directory:
   ```
   [network]
   node_type = miner
   rpc_bind = 127.0.0.1:8545
   p2p_port = 30303
   
   [mining]
   enabled = true
   threads = 1
   machine_id = auto
   
   [storage]
   data_dir = C:\RustChainData
   ```
4. Start the miner:
   ```
   rustchain.exe --config rustchain.conf
   ```

### PowerPC Mac (G3/G4/G5)

1. Download `rustchain-mac-ppc`.
2. Open Terminal and make the binary executable:
   ```bash
   chmod +x ~/Downloads/rustchain-mac-ppc
   ```
3. Create configuration file `~/.rustchain/rustchain.conf`:
   ```
   [network]
   node_type = miner
   rpc_bind = 127.0.0.1:8545
   p2p_port = 30303
   
   [mining]
   enabled = true
   threads = 1
   machine_id = auto
   
   [storage]
   data_dir = /Users/username/Library/RustChainData
   ```
4. Run the miner:
   ```bash
   ./rustchain-mac-ppc --config ~/.rustchain/rustchain.conf
   ```

### Old Linux Desktop

1. Download `rustchain-linux-x86` (or `rustchain-linux-x64`).
2. Make the binary executable:
   ```bash
   chmod +x rustchain-linux-x86
   ```
3. Create configuration file `~/.rustchain/rustchain.conf`:
   ```
   [network]
   node_type = miner
   rpc_bind = 127.0.0.1:8545
   p2p_port = 30303
   
   [mining]
   enabled = true
   threads = 1
   machine_id = auto
   
   [storage]
   data_dir = /home/username/.rustchain/data
   ```
4. Run the miner:
   ```bash
   ./rustchain-linux-x86 --config ~/.rustchain/rustchain.conf
   ```

## Step 3: Verify Mining Status

After starting the miner, check the console output for confirmation:

- **Windows:** Look for "Mining started on machine ID: [UUID]" in the command prompt.
- **macOS/Linux:** Check terminal output for "Node connected to network" and "Mining block [height]".

To verify mining activity, open a web browser and navigate to:
```
http://127.0.0.1:8545/status
```

Expected JSON response:
```json
{
  "status": "mining",
  "machine_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "blocks_mined": 5,
  "balance": "0.000000 RTC",
  "network_peers": 3
}
```

## Step 4: Troubleshooting Common Issues

### Issue: "Cannot connect to network"
- Ensure port 30303 is open in firewall settings.
- Check internet connectivity (wired connection recommended).
- Verify the RustChain network is active (visit `https://rustchain.org/explorer/`).

### Issue: "Insufficient memory"
- Close other applications to free RAM.
- Reduce `threads` to 1 in configuration file.
- For Windows XP, ensure at least 512 MB RAM is available.

### Issue: "Binary not compatible"
- Verify you downloaded the correct architecture version.
- For PowerPC Macs, ensure macOS 10.4+ is installed.
- For Linux, check `glibc` version with `ldd --version`.

### Issue: "Permission denied" (Linux/macOS)
- Run `chmod +x` on the binary.
- If using system-wide installation, run with `sudo`.

## Step 5: Monitor Earnings

RTC tokens are credited to your node's wallet address after each successfully mined block. To check your balance:

1. Access the local RPC endpoint:
   ```
   http://127.0.0.1:8545/wallet/balance
   ```
2. Or use the command-line tool:
   ```bash
   ./rustchain-cli balance
   ```

**Note:** Token distribution occurs after block finalization (approximately 10 minutes per block on the RustChain testnet). Initial earnings may take up to 30 minutes to appear.

## Performance Notes

- **Core 2 Duo laptops:** Expect 1-2 blocks per hour on average.
- **PowerPC G4/G5:** 0.5-1 block per hour; G3 models may be slower.
- **Old Linux desktops:** 1-3 blocks per hour depending on CPU.

The AI-augmented PoRM algorithm prioritizes machine authenticity over raw computational power, so vintage hardware performs competitively.

## Support

For issues or questions:
- Open a GitHub issue: `https://github.com/Scottcjn/Rustchain/issues`
- Join the RustChain Discord: `https://discord.gg/rustchain`
- Check the explorer: `https://rustchain.org/explorer/`

---

*This guide is part of the RustChain Bounty Program. Earn 50 RTC for contributing improvements to this documentation.*