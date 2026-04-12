# BCOS Badge Generator

A standalone web page at `rustchain.org/bcos/badge-generator` that lets users preview and embed BCOS (Beacon Certified Open Source) badges.

## What It Does

- **Enter a Certificate ID** (e.g. `BCOS-ABC123`) or **GitHub repo URL**
- **Preview** the badge in real-time with 4 style variants
- **Copy** markdown or HTML embed code with one click
- **Verify** link to rustchain.org/bcos/verify/{cert_id}

## Files

```
docs/bcos/badge-generator/
└── index.html   # The complete badge generator (static, no backend)
```

## BCOS Badge API Reference

| Endpoint | Description |
|----------|-------------|
| `GET /bcos/badge/{cert_id}.svg` | Returns badge SVG |
| `GET /bcos/badge/{cert_id}.svg?style=flat-square` | Styled variant |
| `GET /bcos/verify/{cert_id}` | Verification page |

### Badge Styles

| Style | shields.io param |
|-------|-----------------|
| flat | (default) |
| flat-square | `?style=flat-square` |
| for-the-badge | `?style=for-the-badge` |
| social | `?style=social` |

## Usage

Open `index.html` in any browser — no build step, no server required.

For deployment, copy `index.html` to `rustchain.org/bcos/badge-generator/` on the web server.

## Bounty

Issue [#2292](https://github.com/Scottcjn/rustchain-bounties/issues/2292) — BCOS v2: Badge generator web tool — 15 RTC
