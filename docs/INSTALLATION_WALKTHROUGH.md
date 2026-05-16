# RustChain Installation Walkthrough

Visual guides for installing RustChain and completing your first attestation.

## 📹 Quick Start Videos

### Miner Installation (45 seconds)

Watch the complete installation process from cloning to running:

[Watch the miner installation recording](asciinema/miner_install.cast)

**What you'll see:**
1. Cloning the RustChain repository
2. Creating Python virtual environment
3. Installing dependencies
4. Configuring environment variables
5. Verifying installation

### First Attestation (52 seconds)

See how to complete your first hardware attestation and start mining:

[Watch the first attestation recording](asciinema/first_attestation.cast)

**What you'll see:**
1. Starting the RustChain miner
2. Viewing the attestation challenge
3. Submitting hardware fingerprint
4. Receiving verification result
5. Checking mining rewards

---

## 🎬 Create Your Own Recordings

### Prerequisites

Install asciinema for terminal recording:

```bash
# macOS
brew install asciinema

# Linux/Windows (via pip)
pip install asciinema
```

### Recording Scripts

We provide scripts to help you create consistent recordings:

| Script | Purpose | Output |
|--------|---------|--------|
| `scripts/asciinema/record_miner_install.sh` | Record installation process | `docs/asciinema/miner_install.cast` |
| `scripts/asciinema/record_first_attestation.sh` | Record first attestation | `docs/asciinema/first_attestation.cast` |
| `scripts/asciinema/convert_to_gif.sh` | Convert .cast to GIF/SVG | `docs/asciinema/*.gif` or `*.svg` |

### Step-by-Step Recording Guide

#### 1. Record Miner Installation

```bash
cd /path/to/rustchain-bounties/issue1615
chmod +x scripts/asciinema/record_miner_install.sh
./scripts/asciinema/record_miner_install.sh
```

This will:
- Check prerequisites
- Start an asciinema recording session
- Guide you through the installation steps
- Save the recording to `docs/asciinema/miner_install.cast`

#### 2. Record First Attestation

```bash
chmod +x scripts/asciinema/record_first_attestation.sh
./scripts/asciinema/record_first_attestation.sh
```

#### 3. Convert to GIF (Optional)

For web-friendly formats:

```bash
# Install svg-term-cli
npm install -g svg-term-cli

# Convert to SVG (recommended for docs)
./scripts/asciinema/convert_to_gif.sh docs/asciinema/miner_install.cast

# Or convert to GIF
./scripts/asciinema/convert_to_gif.sh docs/asciinema/miner_install.cast docs/asciinema/miner_install.gif
```

---

## 📋 Demo Scripts

For consistent demo recordings without actual installation, use the demo scripts:

```bash
# Demo installation (simulated output)
asciinema rec --command "bash scripts/asciinema/demo_miner_install.sh" \
    docs/asciinema/demo_install.cast

# Demo attestation (simulated output)
asciinema rec --command "bash scripts/asciinema/demo_first_attestation.sh" \
    docs/asciinema/demo_attestation.cast
```

---

## 🌐 Embed in Documentation

### GitHub Markdown

GitHub doesn't support direct asciinema embedding, but you can:

1. **Link to the cast file:**
   ```markdown
   [Watch Installation](docs/asciinema/miner_install.cast)
   ```

2. **Convert to GIF and embed:**
   ```markdown
   ![Miner Installation](docs/asciinema/miner_install.gif)
   ```

3. **Use asciinema.org hosting:**
   ```bash
   # Upload to asciinema.org
   asciinema upload docs/asciinema/miner_install.cast
   
   # Then embed with the provided iframe
   ```

### HTML Documentation

For HTML docs, use the asciinema player:

```html
<script src="https://asciinema.org/a/<cast-id>.js" id="<cast-id>" async></script>
```

Or host locally:

```html
<asciinema-player src="docs/asciinema/miner_install.cast"></asciinema-player>
<script src="https://cdn.jsdelivr.net/npm/asciinema-player@3/dist/bundle/asciinema-player.min.js"></script>
```

### README Integration

Add to your README.md:

```markdown
## Installation

See the [Installation Walkthrough](docs/INSTALLATION_WALKTHROUGH.md) for a visual guide with asciinema recordings.

Quick preview:
![Installation Preview](docs/asciinema/miner_install.gif)
```

---

## 📏 File Size Guidelines

To keep repository size manageable:

| Format | Max Size | Recommendation |
|--------|----------|----------------|
| `.cast` (asciinema) | < 100 KB | ✅ Preferred - text-based, scalable |
| `.svg` (svg-term) | < 500 KB | ✅ Good for web - vector format |
| `.gif` (animated) | < 2 MB | ⚠️ Use sparingly - raster format |

### Optimization Tips

1. **Keep recordings short:** Under 60 seconds
2. **Reduce terminal size:** 80x24 or 100x30 characters
3. **Use SVG format:** Smaller and scales better than GIF
4. **Compress GIFs:** Use `gifsicle --optimize=3`
5. **Host large files externally:** Use asciinema.org or YouTube

### Git Configuration

Add to `.gitattributes` to track binary sizes:

```gitattributes
*.cast text
*.gif binary
*.svg text
docs/asciinema/*.gif -diff
```

---

## 🔧 Troubleshooting

### asciinema not found

```bash
# Install via Homebrew (macOS)
brew install asciinema

# Install via pip (all platforms)
pip install asciinema
```

### Recording too large

- Reduce terminal window size before recording
- Shorten the recording duration
- Use faster typing/playback speed: `asciinema rec --speed=2`

### GIF conversion fails

- Ensure svg-term-cli is installed: `npm install -g svg-term-cli`
- Check that the .cast file is valid JSON
- Try alternative: `asciinema play file.cast | gifski -o output.gif`

### Playback issues

```bash
# Verify cast file integrity
asciinema play docs/asciinema/miner_install.cast

# Re-record if corrupted
```

---

## 📚 Related Documentation

- [Console Mining Setup](CONSOLE_MINING_SETUP.md) - Detailed hardware setup
- [Developer Quickstart](DEVELOPER_QUICKSTART.md) - Development environment
- [API Walkthrough](API_WALKTHROUGH.md) - API usage guide
- [Mining Guide](mining.html) - Complete mining documentation

---

## 🎯 Issue #1615

This walkthrough was created for [rustchain-bounties #1615](https://github.com/Scottcjn/rustchain-bounties/issues/1615):

> **Create installation GIFs or asciinema recordings**
> 
> Record miner install + first attestation as asciinema/GIF. 2 RTC.
> 
> Tags: documentation, asciinema, gif, readme, bounty, visual

### Deliverables

- ✅ `docs/asciinema/miner_install.cast` - Installation recording
- ✅ `docs/asciinema/first_attestation.cast` - Attestation recording
- ✅ `scripts/asciinema/record_*.sh` - Recording scripts
- ✅ `scripts/asciinema/demo_*.sh` - Demo scripts
- ✅ `scripts/asciinema/convert_to_gif.sh` - Conversion utility
- ✅ `docs/INSTALLATION_WALKTHROUGH.md` - This documentation

---

© 2026 RustChain Core Team | [Apache License 2.0](../LICENSE)
