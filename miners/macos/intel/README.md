# RustChain Intel Mac Miner

For Intel-based Macs (2013 Mac Pro "Trashcan", MacBook Pro, iMac, etc.)

## Supported Hardware
- Mac Pro 2013 (Trashcan) - Intel Xeon E5
- MacBook Pro (Intel)
- iMac (Intel)
- Mac mini (Intel)

## Known Deployments
| Hostname | IP | CPU | OS |
|----------|-----|-----|-----|
| Sophias-Mac-Trashcan.local | 192.168.0.153 | Intel Xeon E5-1650 v2 | macOS Monterey |

## Installation
```bash
# Copy miner
scp rustchain_mac_miner_v2.4.py user@mac:~/rustchain_mac_miner.py
scp fingerprint_checks.py user@mac:~/fingerprint_checks.py

# Install launchd for auto-start
# See ../launchd/com.rustchain.miner.plist
```

## Multiplier
- Intel Mac: 0.8x (modern architecture)
- Mac Pro 2013: May qualify for retro bonus in future RIPs
