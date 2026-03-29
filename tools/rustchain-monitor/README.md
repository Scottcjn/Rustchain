# RustChain Monitor

CLI tool for monitoring the RustChain network health, active miners, and epoch information.

## Installation

```bash
pip install rustchain-monitor
```

Or run directly:

```bash
python3 rustchain_monitor.py
```

## Usage

```bash
# Show full status (health + miners + epoch)
rustchain-monitor

# Just health check
rustchain-monitor --health

# List active miners
rustchain-monitor --miners

# Show current epoch
rustchain-monitor --epoch
```

## Sample Output

```
✅ Node is healthy
   Version: 2.2.1-rip200
   Uptime: 150109s (41.7 hours)
   Backup age: 14.41 hours
   DB RW: True

📊 Active miners: 24
   Recent miners:
   - RTC14f06ee... HW: Unknown/Other             Multiplier: 0.001
   - modern-sophia-Pow... HW: x86-64 (Modern)     Multiplier: 1.05
   ...

🕐 Epoch: 116 (slot 16832, pot 1.5 RTC, enrolled: 26)
```

## Bounty

This tool was created as part of the RustChain bounty program (Standard tier, 20-50 RTC). See [bounty issues](https://github.com/Scottcjn/Rustchain/issues?q=is%3Aissue+is%3Aopen+label%3Abounty).

## License

MIT
