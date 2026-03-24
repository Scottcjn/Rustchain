# RustChain Miner Setup Wizard (Bounty #47)

Single-file browser wizard for miner onboarding.

## File

- `index.html` (self-contained static page, no build step)

## What it covers

1. Platform detection (OS/arch from User-Agent)
2. Python check commands (Linux/macOS)
3. Wallet setup (generate/import flow with seed phrase display)
4. Miner download/install command generation
5. Configuration (wallet + node URL)
6. Connection test (`/health`)
7. First attestation verification (`/api/miners` lookup)

## Notes

- Designed to run locally in browser and on GitHub Pages.
- No backend required; pure client-side HTML/CSS/JS.
- If cross-origin fetch is blocked by CORS, use terminal command checks (`curl -sk ...`).

## Run locally

Open directly in a browser:

```bash
open docs/miner-setup-wizard/index.html
```

or serve static files:

```bash
python3 -m http.server 8000
# then open http://localhost:8000/docs/miner-setup-wizard/index.html
```
