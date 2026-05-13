# RustChain Vintage Miner Setup Guide

## Bounty: 50 RTC — "Mine Your Grandma's Computer"

This guide provides step-by-step instructions to set up a RustChain miner on vintage hardware. The process targets three common legacy platforms and should take under 15 minutes per machine.

---

## Prerequisites

Before starting, ensure you have:

- A vintage computer with internet access (wired Ethernet recommended)
- A RustChain wallet address (generate one at [rustchain.org/wallet](https://rustchain.org/wallet) or via CLI)
- Basic familiarity with command-line interfaces
- The RustChain miner binary for your platform (download from [releases](https://github.com/Scottcjn/Rustchain/releases))

---

## Platform-Specific Guides

### 1. Old Windows Laptop (Core 2 Duo Era)

**Target hardware:** Windows XP/Vista/7, Intel Core 2 Duo, 2GB+ RAM

**Steps:**

1. **Download the miner:**
   - Visit [releases page](https://github.com/Scottcjn/Rustchain/releases)
   - Download `rustchain-miner-win32-v1.0.0.zip` (32-bit) or `rustchain-miner-win64-v1.0.0.zip` (64-bit)

2. **Extract the archive:**
   ```cmd
   mkdir C:\RustChainMiner
   cd C:\RustChainMiner
   tar -xf C:\Downloads\rustchain-miner-win64-v1.0.0.zip
   ```

3. **Configure the miner:**
   Create `config.toml` in the miner directory:
   ```toml
   [network]
   node = "seed.rustchain.org:8333"
   
   [miner]
   wallet = "YOUR_WALLET_ADDRESS"
   threads = 2
   cpu_usage = 0.5
   ```

4. **Run the miner:**
   ```cmd
   rustchain-miner.exe --config config.toml
   ```

**Expected output:**
```
[INFO] Connecting to seed.rustchain.org:8333...
[INFO] Connected to network (height: 123456)
[INFO] Mining started with 2 threads
[INFO] Share found! Submitting to pool...
```

---

### 2. PowerPC Mac (G3/G4/G5)

**Target hardware:** Mac OS X 10.4–10.5, PowerPC G4/G5, 512MB+ RAM

**Steps:**

1. **Download the PowerPC binary:**
   - From [releases](https://github.com/Scottcjn/Rustchain/releases), download `rustchain-miner-ppc-macos-v1.0.0.tar.gz`

2. **Extract and prepare:**
   ```bash
   cd ~/Desktop
   tar -xzf ~/Downloads/rustchain-miner-ppc-macos-v1.0.0.tar.gz
   cd rustchain-miner-ppc-macos
   chmod +x rustchain-miner
   ```

3. **Create configuration:**
   ```bash
   cat > config.toml << EOF
   [network]
   node = "seed.rustchain.org:8333"
   
   [miner]
   wallet = "YOUR_WALLET_ADDRESS"
   threads = 1
   cpu_usage = 0.6
   EOF
   ```

4. **Run the miner:**
   ```bash
   ./rustchain-miner --config config.toml
   ```

**Note:** PowerPC G3/G4 may require `threads = 1` due to single-core limitations. G5 dual-core can use `threads = 2`.

---

### 3. Old Linux Desktop

**Target hardware:** Ubuntu 12.04+/Debian 7+/CentOS 6+, 1GB+ RAM, x86 or x86_64

**Steps:**

1. **Install dependencies:**
   ```bash
   # Debian/Ubuntu
   sudo apt-get update
   sudo apt-get install -y libssl-dev libcurl4-openssl-dev
   
   # CentOS/RHEL
   sudo yum install -y openssl-devel libcurl-devel
   ```

2. **Download the Linux binary:**
   ```bash
   wget https://github.com/Scottcjn/Rustchain/releases/download/v1.0.0/rustchain-miner-linux-x86_64-v1.0.0.tar.gz
   tar -xzf rustchain-miner-linux-x86_64-v1.0.0.tar.gz
   cd rustchain-miner-linux-x86_64
   ```

3. **Configure:**
   ```bash
   cat > config.toml << EOF
   [network]
   node = "seed.rustchain.org:8333"
   
   [miner]
   wallet = "YOUR_WALLET_ADDRESS"
   threads = $(nproc)
   cpu_usage = 0.7
   EOF
   ```

4. **Run as background service:**
   ```bash
   nohup ./rustchain-miner --config config.toml > miner.log 2>&1 &
   ```

5. **Monitor:**
   ```bash
   tail -f miner.log
   ```

---

## Verification

After starting the miner, verify it's working:

1. **Check miner status:**
   ```bash
   # Linux/Mac
   ps aux | grep rustchain-miner
   
   # Windows (Task Manager)
   tasklist | findstr rustchain
   ```

2. **View logs for shares found:**
   Look for lines containing `Share found!` in the miner output.

3. **Check wallet balance:**
   Visit [rustchain.org/explorer](https://rustchain.org/explorer/) and enter your wallet address.

---

## Troubleshooting

| Symptom | Solution |
|---------|----------|
| `Connection refused` | Check firewall allows outbound TCP/8333 |
| `No shares found after 10 minutes` | Reduce `threads` or `cpu_usage` in config |
| `Segmentation fault` | Use 32-bit binary on 32-bit OS |
| `Permission denied` | Run `chmod +x rustchain-miner` on Linux/Mac |
| `High CPU temperature` | Reduce `cpu_usage` to 0.3–0.5 |

---

## Performance Expectations

| Hardware | Expected Hashrate | Daily RTC (est.) |
|----------|-------------------|------------------|
| Core 2 Duo (2.0 GHz) | 2–4 H/s | 0.5–1.0 RTC |
| PowerPC G5 (2.0 GHz) | 1–2 H/s | 0.3–0.6 RTC |
| Pentium 4 (3.0 GHz) | 0.5–1 H/s | 0.1–0.3 RTC |

*Actual earnings vary based on network difficulty and uptime.*

---

## Support

- **GitHub Issues:** [github.com/Scottcjn/Rustchain/issues](https://github.com/Scottcjn/Rustchain/issues)
- **Discord:** [discord.gg/rustchain](https://discord.gg/rustchain)
- **Documentation:** [docs.rustchain.org](https://docs.rustchain.org)

---

*This guide is part of the RustChain Bounty Program. Submit your completed guide as a pull request to claim 50 RTC.*