# Troubleshooting Guide

## Common Issues

### Build Issues

#### "mips-linux-gnu-gcc: command not found"

**Solution:** Install MIPS cross-compiler.

```bash
# Ubuntu/Debian
sudo apt-get install gcc-mips-linux-gnu

# Or use PSn00bSDK
git clone https://github.com/LM-Softland/PSn00bSDK
cd PSn00bSDK && make && sudo make install
```

#### "psxgpu.h: No such file or directory"

**Solution:** Install PS1 SDK headers.

```bash
# PSn00bSDK includes these
export PSNOOBSDK=/opt/PSn00bSDK
export CFLAGS="-I$PSNOOBSDK/include"
```

#### Linker errors about missing libraries

**Solution:** Ensure PS1 SDK libraries are installed.

```bash
ls $PSNOOBSDK/lib/libpsx*.a
# Should show: libpsxgpu.a, libpsxapi.a, libpsxpad.a
```

### Serial Connection Issues

#### "Port COM3 not found" (Windows)

**Solutions:**
1. Check Device Manager → Ports (COM & LPT)
2. Try a different USB port
3. Install adapter drivers (CP210x, CH340, FTDI)
4. Use `python bridge.py --list-ports` to see available ports

#### "Permission denied" (Linux)

**Solution:** Add user to dialout group.

```bash
sudo usermod -a -G dialout $USER
# Log out and back in
```

Or use sudo:
```bash
sudo python bridge.py -p /dev/ttyUSB0
```

#### No data received from PS1

**Checklist:**
- [ ] TX and RX are crossed (TX→RX, RX→TX)
- [ ] GND is connected
- [ ] Baud rate matches (9600)
- [ ] PS1 miner is actually running
- [ ] Serial adapter is 3.3V compatible

#### Garbled text output

**Causes:**
- Wrong baud rate
- Wrong serial settings (should be 8N1)
- Voltage mismatch (5V vs 3.3V)

**Solution:**
```python
# Verify settings
ser = serial.Serial(
    port='COM3',
    baudrate=9600,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE
)
```

### Attestation Issues

#### "Attestation rejected: invalid_fingerprint"

**Cause:** Emulator detected or fingerprint validation failed.

**Solutions:**
1. Run on real PS1 hardware (not emulator)
2. Check that fingerprint collection is working
3. Verify CD-ROM timing is non-zero

#### "Attestation rejected: unknown_wallet"

**Solution:** Register your wallet first.

```bash
# Create wallet via clawrtc
pip install clawrtc
clawrtc wallet create --name ps1-miner
```

#### "Connection timeout"

**Causes:**
- Node is down
- Network issue
- Firewall blocking

**Solutions:**
1. Check node status: `curl -k https://rustchain.org/health`
2. Try different network
3. Check firewall settings

### PS1-Specific Issues

#### Miner crashes on startup

**Causes:**
- Memory corruption
- Invalid binary format
- Hardware incompatibility

**Solutions:**
1. Rebuild with `make clean && make`
2. Test in DuckStation emulator first
3. Try different PS1 model

#### Memory card save fails

**Causes:**
- Card is full
- Card is corrupted
- Directory doesn't exist

**Solutions:**
1. Format memory card
2. Check free space: `memcard_free_space()`
3. Ensure directory creation: `memcard_mkdir("bu00:RUSTCHN")`

#### Serial output but no attestation

**Cause:** Network bridge not running.

**Solution:** Start the PC bridge:
```bash
cd ps1_bridge
python bridge.py -p COM3
```

### Bridge Issues

#### "Failed to connect to node"

**Solutions:**
1. Check internet connection
2. Verify node URL: `https://rustchain.org`
3. Check if node is online

#### Wallet file not found

**Solution:** Create wallet file manually.

```bash
echo '{"wallet": "ps1-miner", "created": "2026-03-13"}' > ps1_wallet.json
```

#### Epoch counter resets

**Cause:** Bridge restarted.

**Solution:** This is normal. The node tracks epochs, not the bridge.

## Debug Mode

### Enable verbose logging

**Bridge:**
```bash
python bridge.py -p COM3 -v  # Verbose mode
```

**PS1 Miner:**
Edit `main.c`:
```c
#define DEBUG 1
```

### Capture serial traffic

**Linux:**
```bash
# Monitor serial port
screen /dev/ttyUSB0 9600
```

**Windows:**
```powershell
# Use PuTTY or Tera Term
# Connect to COM3 @ 9600
```

### Check node logs

```bash
curl -k https://rustchain.org/health
curl -k https://rustchain.org/epoch
```

## Performance Optimization

### Faster serial communication

Increase baud rate (both PS1 and bridge):

**PS1 Miner:**
```c
serial_init(19200);  // or 38400, 57600, 115200
```

**Bridge:**
```bash
python bridge.py -p COM3 -b 115200
```

### Reduce memory usage

In `main.c`, reduce buffer sizes:
```c
#define SERIAL_BUFFER_SIZE 128  // Was 256
```

### Faster fingerprint collection

Reduce sample counts in `fingerprint.c`:
```c
// Fewer samples = faster but less accurate
for (int i = 0; i < 100; i++)  // Was 1000
```

## Getting Help

### Resources

- [RustChain Discord](https://discord.gg/VqVVS2CW9Q)
- [GitHub Issues](https://github.com/Scottcjn/Rustchain/issues)
- [PSn00bSDK Documentation](https://github.com/LM-Softland/PSn00bSDK)

### Information to Include

When reporting issues, provide:

1. **PS1 model:** SCPH-XXXX
2. **Build environment:** OS, compiler version
3. **Serial adapter:** Type (CP2102, FTDI, etc.)
4. **Error messages:** Full output
5. **What you tried:** Steps already taken

### Example Bug Report

```
**Issue:** Attestation fails with "invalid_fingerprint"

**PS1 Model:** SCPH-1001 (US)
**Build:** Ubuntu 22.04, mips-linux-gnu-gcc 11.2.0
**Serial:** CP2102 USB-to-TTL

**Error:**
[BRIDGE] Attestation rejected: invalid_fingerprint

**Tried:**
- Rebuilt miner
- Tested on real hardware (not emulator)
- Verified serial connection works

**Logs:**
[Attached full output]
```

## Known Limitations

1. **Slow attestation:** Serial at 9600 bps takes ~30 seconds
2. **Memory constraints:** Only 2 MB RAM limits features
3. **No FPU:** SHA-256 is software-only
4. **Emulator detection:** Most emulators will be rejected

## Future Improvements

- [ ] Support for PS1 Network Adapter (Ethernet)
- [ ] Faster serial rates (115200 bps)
- [ ] Memory card batch attestation
- [ ] LCD display for status
- [ ] Dual PS1 mining (link cable)

---

*Still having issues? Join the Discord and ask for help!* 🦀
