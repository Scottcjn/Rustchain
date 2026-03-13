# RustChain Asciinema Recordings

This directory contains terminal recordings for RustChain documentation.

## Files

| File | Description | Duration | Size |
|------|-------------|----------|------|
| `miner_install.cast` | Complete miner installation process | ~45s | ~5 KB |
| `first_attestation.cast` | First hardware attestation flow | ~52s | ~6 KB |

## Format

Files use the [asciinema cast v2 format](https://github.com/asciinema/asciinema/blob/develop/doc/asciicast-v2.md) - a JSON-based text format that records:
- Terminal output
- Timing information
- Escape sequences for colors and formatting

## Playback

```bash
# Install asciinema
brew install asciinema  # macOS
pip install asciinema   # Linux/Windows

# Play recordings
asciinema play miner_install.cast
asciinema play first_attestation.cast
```

## Conversion

Convert to web-friendly formats:

```bash
# To SVG (recommended for docs)
npm install -g svg-term-cli
svg-term --in=miner_install.cast --out=miner_install.svg

# To GIF (requires additional tools)
./../../scripts/asciinema/convert_to_gif.sh miner_install.cast miner_install.gif
```

## Recording Your Own

See the recording scripts in `../../scripts/asciinema/`:

```bash
# Record installation
../../scripts/asciinema/record_miner_install.sh

# Record attestation
../../scripts/asciinema/record_first_attestation.sh
```

## File Size Guidelines

- Keep recordings under 60 seconds
- Target terminal size: 100x30 or smaller
- Prefer .cast format (text-based, ~5-10 KB)
- Convert to SVG for web embedding (~50-200 KB)
- Use GIF sparingly (< 2 MB max)

## Embedding

### GitHub Markdown
GitHub doesn't support direct asciinema embedding. Options:
1. Link to the .cast file
2. Convert to GIF and embed as image
3. Upload to asciinema.org and embed via iframe

### HTML Documentation
```html
<asciinema-player src="miner_install.cast"></asciinema-player>
<script src="https://cdn.jsdelivr.net/npm/asciinema-player@3/dist/bundle/asciinema-player.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/asciinema-player@3/dist/bundle/asciinema-player.css" />
```

## License

Same as RustChain project (Apache License 2.0)
