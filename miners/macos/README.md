# RustChain macOS Miners

## Supported Platforms

### Apple Silicon (M1/M2/M3)
- `rustchain_mac_miner_v2.4.py` - Universal miner with fingerprint attestation
- Multiplier: 0.8x (modern)

### Intel Mac
- `intel/rustchain_mac_miner_v2.4.py` - Same miner, works on Intel
- See `intel/README.md` for deployment details
- Multiplier: 0.8x (modern)

### PowerPC (G4/G5)
- See `../ppc/` for native C miners
- Multiplier: G4 2.5x, G5 2.0x (antiquity bonus)

## Auto-Start (launchd)
Copy `launchd/com.rustchain.miner.plist` to `~/Library/LaunchAgents/`
and update paths for your username.

```bash
# Install
cp launchd/com.rustchain.miner.plist ~/Library/LaunchAgents/
# Edit paths in plist, then:
launchctl load ~/Library/LaunchAgents/com.rustchain.miner.plist
```

## Known Deployments
| Host | IP | Type | CPU | Status |
|------|-----|------|-----|--------|
| Sophimacs-Mac-mini | .134 | M2 | Apple M2 | Active |
| Sophias-Mac-Trashcan | .153 | Intel | Xeon E5-1650 v2 | Active |
