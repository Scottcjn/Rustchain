# Build Requirements

To build the RustChain GBC miner ROM, you'll need:

## Toolchain

### Option 1: GBDK (Recommended)

```bash
# Ubuntu/Debian
sudo apt-get install gbdk

# macOS (Homebrew)
brew install gbdk

# Windows
# Download from: https://gbdk.sourceforge.net/
```

### Option 2: RGBDS

```bash
# Ubuntu/Debian
sudo apt-get install rgbds

# macOS (Homebrew)
brew install rgbds

# Windows
# Download from: https://github.com/gbdev/rgbds/releases
```

## Build Commands

### Using GBDK

```bash
make build-gbdk
```

### Using RGBDS

```bash
make build-rgbds
```

## Output

- `rustchain_gbc.gb` - Game Boy Color ROM (128 KB)
- `rustchain_gbc.sym` - Symbol file for debugging
- `rustchain_gbc.map` - Memory map

## Flashing to Cartridge

### Everdrive GB X7

1. Copy `rustchain_gbc.gb` to microSD card
2. Insert microSD into Everdrive
3. Insert Everdrive into GBC
4. Select ROM from menu

### GB Flash Cart (Generic)

1. Use flash cart utility to write ROM
2. Follow manufacturer instructions

## Testing

### Emulator (for development only)

```bash
# SameBoy
sameboy rustchain_gbc.gb

# Gambatte
gambatte rustchain_gbc.gb

# Note: Emulators will be detected and receive minimal rewards
```

### Real Hardware

1. Flash ROM to cartridge
2. Insert into GBC
3. Connect link cable
4. Run bridge software: `python3 gbc_bridge.py --port COM3 --wallet YOUR_WALLET`

## Debugging

### Emulator Debugging

```bash
# BGB emulator with debug
bgb -debug rustchain_gbc.gb

# View memory, registers, breakpoints
```

### Serial Output

Enable debug output in bridge software:

```bash
python3 gbc_bridge.py --port COM3 --wallet YOUR_WALLET --debug
```

## Troubleshooting

### Build Errors

- **Missing header**: Ensure GBDK/RGBDS is in PATH
- **Syntax errors**: Check assembly syntax for your assembler
- **Memory overflow**: Reduce ROM size or optimize code

### Runtime Errors

- **GBC not detected**: Check cable connection
- **Attestation fails**: Verify cartridge RAM is working
- **Link errors**: Try different baud rate

## Performance Optimization

For best performance on GBC:

1. Use WRAM0/WRAM1 efficiently
2. Minimize ROM bank switches
3. Use hardware registers directly
4. Optimize inner loops
5. Use STOP instruction for power saving

## File Sizes

- ROM: 128 KB (MBC1)
- RAM: 32 KB (internal) + 8 KB (cartridge)
- Save: 8 KB (battery backed)
