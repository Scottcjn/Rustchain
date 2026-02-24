# RustChain Mining Badge GitHub Action

Display a live RustChain mining status badge in any repository README. Every repo using this = backlink to RustChain.

## Features

- 🎨 Dynamic SVG badge showing:
  - Miner wallet balance (RTC)
  - Current epoch
  - Mining status (Active/New)
- 🔄 Auto-updates via GitHub Actions
- 🛡️ Shields.io compatible
- 📊 GitHub Actions summary report

## Usage

### Option 1: Badge URL (Simple)

Add this to your README:

```markdown
![RustChain Mining](https://img.shields.io/endpoint?url=https://50.28.86.131/api/badge/YOUR_WALLET)
```

### Option 2: GitHub Action (Auto-update)

Create `.github/workflows/rustchain-badge.yml`:

```yaml
name: RustChain Badge
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:

jobs:
  update-badge:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Update RustChain Badge
        uses: Scottcjn/rustchain-badge-action@v1
        with:
          wallet: 'YOUR_WALLET_NAME'
          
      - name: Commit badge
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add rustchain-badge.json
          git diff --quiet && git diff --staged --quiet || git commit -m "Update RustChain badge"
          git push
```

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `wallet` | ✅ | - | Your RustChain miner wallet name |
| `node-url` | ❌ | `https://50.28.86.131` | RustChain node URL |
| `badge-style` | ❌ | `flat` | Shields.io badge style |

## Outputs

| Output | Description |
|--------|-------------|
| `badge-url` | URL to the generated shields.io badge |
| `balance` | Current wallet balance |
| `epoch` | Current RustChain epoch |

## Example Output

![RustChain](https://img.shields.io/badge/⛏️%20RustChain-42.5%20RTC%20|%20Epoch%2073%20|%20Active-brightgreen)

## Development

```bash
# Install dependencies
npm install

# Build
npm run build

# Test
npm test
```

## License

MIT - See [LICENSE](LICENSE) for details.

## About RustChain

[RustChain](https://github.com/Scottcjn/Rustchain) is a Proof-of-Antiquity blockchain where vintage hardware earns more than modern GPUs. Fair launch, fixed supply (8.3M RTC), no VC funding.

- Website: https://rustchain.org
- Start mining: `pip install clawrtc`