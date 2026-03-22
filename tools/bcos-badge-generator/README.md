# BCOS Badge Generator

Static HTML/JS badge generator for BCOS (Beacon Certified Open Source) certification badges.

## Quick Start

Open `index.html` in a web browser, or deploy to `rustchain.org/bcos/badge-generator`.

## Features

- **Input Options**: Certificate ID (cert_id) or Repository URL
- **Live Preview**: Fetches badge from `GET /bcos/badge/{cert_id}.svg`
- **Badge Styles**: flat, flat-square, for-the-badge
- **Embed Codes**: Markdown and HTML output
- **Vintage Terminal Aesthetic**: Retro CLI-inspired UI

## Usage

### 1. Enter Certificate ID

Input your BCOS certificate ID in the format `BCOS-xxxxxxxx` (8 hex characters).

### 2. Select Badge Style

Choose from three styles:
- `flat` — Default rounded style with gradient
- `flat-square` — Square corners, flat colors
- `for-the-badge` — Larger, badge-style format

### 3. Preview Badge

Click "Generate Badge" to fetch and preview the badge from the BCOS API endpoint.

### 4. Copy Embed Code

Use the generated Markdown or HTML code in your README:

**Markdown:**
```markdown
[![BCOS](https://50.28.86.131/bcos/badge/BCOS-xxx.svg)](https://rustchain.org/bcos/verify/BCOS-xxx)
```

**HTML:**
```html
<a href="https://rustchain.org/bcos/verify/BCOS-xxx" target="_blank" rel="noopener">
  <img src="https://50.28.86.131/bcos/badge/BCOS-xxx.svg" alt="BCOS Certified" />
</a>
```

## API Endpoint

The badge generator uses the following endpoint:

```
GET /bcos/badge/{cert_id}.svg
```

**Parameters:**
- `cert_id` — BCOS certificate ID (e.g., `BCOS-12345678`)
- `style` (optional) — Badge style: `flat`, `flat-square`, `for-the-badge`

**Example:**
```
https://50.28.86.131/bcos/badge/BCOS-12345678.svg?style=flat
```

## Configuration

Edit the `BADGE_ENDPOINT` and `VERIFY_BASE_URL` constants in `index.html`:

```javascript
const BADGE_ENDPOINT = 'https://50.28.86.131/bcos/badge';
const VERIFY_BASE_URL = 'https://rustchain.org/bcos/verify';
```

## Deployment

### Static Hosting

Deploy `index.html` to any static hosting service:

```bash
# Example: Deploy to rustchain.org/bcos/badge-generator/
cp index.html /path/to/rustchain.org/bcos/badge-generator/index.html
```

### Local Testing

Open directly in a browser:
```bash
open tools/bcos-badge-generator/index.html
```

Or serve locally:
```bash
cd tools/bcos-badge-generator
python -m http.server 8000
# Visit http://localhost:8000
```

## File Structure

```
tools/bcos-badge-generator/
├── index.html          # Main application (single-file HTML/JS)
└── README.md           # This documentation
```

## Validation

Run the validation script to verify file integrity:

```bash
python tools/validate_bcos_generator.py
```

**Checks:**
- ✅ File exists
- ✅ Valid HTML structure
- ✅ Contains required elements
- ✅ JavaScript is syntactically correct
- ✅ CSS is syntactically correct

## Browser Support

- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+

## Requirements

- Modern web browser with JavaScript enabled
- Access to BCOS badge API endpoint

## Troubleshooting

### Preview Not Loading

If the badge preview shows a warning, the API endpoint may be unavailable. The embed codes will still work when the endpoint is accessible.

### Invalid Certificate ID

Ensure the format is exactly `BCOS-xxxxxxxx` where `x` is a hexadecimal character (0-9, a-f).

## License

MIT License — See [LICENSE](../../LICENSE) for details.

## Related

- [BCOS Specification](../../docs/BEACON_CERTIFIED_OPEN_SOURCE.md)
- [BCOS Verification](https://rustchain.org/bcos/verify/)
- [RustChain](https://rustchain.org)

---

**BCOS — Beacon Certified Open Source**  
Part of the [RustChain](https://rustchain.org) ecosystem by [Elyan Labs](https://elyanlabs.ai)
