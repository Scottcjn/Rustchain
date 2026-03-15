# RustChain Documentation Site

MkDocs-powered documentation site for [RustChain](https://github.com/Scottcjn/Rustchain), the Proof-of-Antiquity blockchain.

## Setup

```bash
pip install mkdocs mkdocs-material mkdocs-minify-plugin
```

## Development

Serve locally with live reload:

```bash
cd docs-site
mkdocs serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

## Build

Generate static files:

```bash
cd docs-site
mkdocs build
```

Output is written to `docs-site/site/`.

## Deploy to GitHub Pages

```bash
cd docs-site
mkdocs gh-deploy
```

## Structure

```
docs-site/
├── mkdocs.yml              # MkDocs configuration (Material theme)
├── docs/
│   ├── index.md            # Landing page
│   ├── getting-started.md  # Quickstart and installation guide
│   ├── mining.md           # Mining guide and reward multipliers
│   ├── architecture.md     # System architecture and protocol design
│   ├── api-reference.md    # REST API documentation
│   ├── contributing.md     # Contribution guide and bounty tiers
│   └── faq.md              # Frequently asked questions
└── README.md               # This file
```

## Links

- **RustChain**: [rustchain.org](https://rustchain.org)
- **GitHub**: [Scottcjn/Rustchain](https://github.com/Scottcjn/Rustchain)
- **Discord**: [discord.gg/VqVVS2CW9Q](https://discord.gg/VqVVS2CW9Q)
