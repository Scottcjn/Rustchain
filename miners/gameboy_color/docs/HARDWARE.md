# Hardware Setup Guide

## Required Hardware

### 1. Game Boy Color Console

- Original Nintendo Game Boy Color (1998)
- Any color variant works
- Battery should be charged or use AC adapter
- **Alternative**: Game Boy Advance (backward compatible)

### 2. Flash Cartridge

**Recommended**: Everdrive GB X7
- Supports up to 8 MB ROMs
- Battery-backed save
- Easy microSD card loading
- Price: ~$100-150

**Budget Option**: Generic GB Flash Cart
- Supports up to 512 KB ROMs
- May require special software
- Price: ~$30-50

### 3. Link Cable + USB Adapter

**Option A**: Official Nintendo GB Link Cable + USB Adapter
- Nintendo Game Boy Link Cable (DMG-04)
- GB Link Cable to USB adapter
- Most reliable option

**Option B**: Third-Party USB Link Cable
- Search: "Game Boy Link Cable USB"
- Ensure compatibility with GBC
- Price: ~$20-40

**Option C**: Raspberry Pi Pico Bridge
- Build your own USB adapter
- See `../pico_bridge/` for firmware
- Most flexible option

### 4. Host Computer

- Windows, macOS, or Linux
- USB port for link cable adapter
- Python 3.8+ for bridge software
- Internet connection for RustChain API

## Setup Steps

### Step 1: Prepare Flash Cartridge

1. **Format microSD card** (FAT32)
2. **Copy ROM**: Copy `rustchain_gbc.gb` to microSD
3. **Insert microSD** into flash cartridge
4. **Test boot**: Insert into GBC and power on

### Step 2: Connect Link Cable

1. **Connect to GBC**: Plug link cable into GBC EXT port
2. **Connect to PC**: Plug USB adapter into computer
3. **Verify connection**: 
   - Windows: Check Device Manager for COM port
   - Linux: Check `/dev/ttyUSB*` or `/dev/ttyACM*`
   - macOS: Check `/dev/tty.usbserial*`

### Step 3: Install Bridge Software

```bash
# Navigate to bridge directory
cd miners/gameboy_color/bridge

# Install dependencies
pip install -r requirements.txt

# Test connection
python3 gbc_bridge.py --list-ports
```

### Step 4: Configure Wallet

Create or use existing RustChain wallet:

```bash
# Create new wallet (if needed)
clawrtc wallet create --name gbc-miner

# Or use existing wallet
# Wallet address format: RTC...
```

### Step 5: Start Mining

```bash
# Start mining
python3 gbc_bridge.py \
  --port COM3 \
  --wallet RTC4325af95d26d59c3ef025963656d22af638bb96b
```

## Connection Diagram

```
┌─────────────────┐
│  Game Boy Color │
│                 │
│  [Cartridge]    │◄── Flash cart with rustchain_gbc.gb
│                 │
│  [EXT Port]     │
└────────┬────────┘
         │
         │ GB Link Cable
         │
         ▼
┌─────────────────┐
│  USB Adapter    │
│  (Link→USB)     │
└────────┬────────┘
         │
         │ USB
         │
         ▼
┌─────────────────┐
│  Host PC        │
│                 │
│  gbc_bridge.py  │◄── Bridge software
│                 │
│  Internet       │◄── RustChain API
└─────────────────┘
```

## Troubleshooting

### GBC Won't Boot

1. **Check cartridge**: Reseat flash cartridge
2. **Check battery**: Charge GBC or use AC adapter
3. **Check ROM**: Verify ROM was copied correctly
4. **Try emulator**: Test ROM in emulator first

### Link Cable Not Detected

**Windows**:
```
1. Open Device Manager
2. Look under "Ports (COM & LPT)"
3. Note COM port number (e.g., COM3)
4. Use: python3 gbc_bridge.py --port COM3
```

**Linux**:
```bash
# List USB devices
lsusb

# Check serial ports
ls -la /dev/ttyUSB*
ls -la /dev/ttyACM*

# May need to add user to dialout group
sudo usermod -a -G dialout $USER
```

**macOS**:
```bash
# List serial devices
ls -la /dev/tty.*

# Common names:
# /dev/tty.usbserial
# /dev/tty.usbmodem
```

### Attestation Fails

1. **Check connection**: Ensure link cable is secure
2. **Check GBC screen**: Should show "Connected" or similar
3. **Try diagnostics**: `python3 gbc_bridge.py --port COM3 --wallet ... --diagnose`
4. **Check cartridge RAM**: Some flash carts have RAM issues

### Low Hash Rate

- **Normal**: GBC is slow (~0.3 hashes/epoch)
- **Check power**: Weak battery can cause slowdowns
- **Check temperature**: GBC may throttle when hot

## Power Consumption

| Component | Power |
|-----------|-------|
| GBC Console | ~0.5W |
| Flash Cart | ~0.1W |
| Link Cable | ~0.1W |
| **Total** | **~0.7W** |

**Annual Power Cost**: ~$0.60 (at $0.10/kWh)

## Expected Earnings

With 2.6× antiquity multiplier:

- **Per Epoch**: ~0.31 RTC
- **Per Day**: ~45 RTC
- **Per Month**: ~1,350 RTC
- **Per Year**: ~16,425 RTC

*Actual rewards vary based on network participation*

## Maintenance

### Weekly

- Check GBC battery level
- Verify bridge software is running
- Check wallet balance

### Monthly

- Clean GBC cartridge contacts
- Update bridge software
- Review mining statistics

### Yearly

- Replace GBC battery (if applicable)
- Check flash cartridge battery
- Update GBC ROM if new version available

## Safety

- **Don't overclock**: GBC should run at stock 8.4 MHz
- **Avoid heat**: Don't leave GBC in direct sunlight
- **Use surge protector**: Protect host PC
- **Backup saves**: Cartridge RAM can fail

## Advanced: Custom Hardware

### Raspberry Pi Pico Bridge

See `../pico_bridge/` for DIY USB adapter using Raspberry Pi Pico.

### Direct GPIO Connection

For hardware hackers: Connect GBC link cable directly to Raspberry Pi GPIO.

### Multiple GBC Setup

Run multiple bridge instances for multiple GBC consoles:

```bash
# Terminal 1
python3 gbc_bridge.py --port COM3 --wallet WALLET1

# Terminal 2
python3 gbc_bridge.py --port COM4 --wallet WALLET2
```

Each GBC needs unique hardware ID and wallet.

## Support

- **Documentation**: See README.md
- **Issues**: GitHub Issues
- **Discord**: https://discord.gg/VqVVS2CW9Q

---

**Happy Mining! 🎮⛏️**
