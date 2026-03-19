# BCOS Certified Directory

**Blockchain Certified Open Source** — a curated, verifiable directory of projects in the RustChain ecosystem.

**Bounty:** #301 — https://github.com/Scottcjn/rustchain-bounties/issues/301

---

## BCOS Tiers

| Tier | Name | Description |
|------|------|-------------|
| **L0** | Community Reviewed | Basic review — functional and open source |
| **L1** | BCOS Verified | Reviewed and verified by BCOS committee |
| **L2** | BCOS Certified | Fully audited, SBOM published, attested SHA tracked |

---

## Directory Structure

```
bcos-directory/
├── index.html          # Live site (fetches data/projects.json)
├── data/
│   └── projects.json   # Project data — edit this to add/remove projects
├── build.py            # Build script: generates dist/index.html
├── dist/
│   └── index.html      # Self-contained build (no server needed)
└── README.md
```

---

## Adding a New Project

**Step 1:** Add entry to `data/projects.json`

```json
{
  "id": "bcos-XXX",
  "name": "Your Project Name",
  "url": "https://your-project.io",
  "github": "https://github.com/your-org/your-repo",
  "bcos_tier": "L0",
  "category": "agent-infra",
  "latest_attested_sha": "abc123...",
  "sbom_hash": "sha256:...",
  "review_note": "One-line description of what this project does.",
  "attested_at": "2026-03-19",
  "reviewer": "your_name",
  "badges": []
}
```

**Step 2:** Submit a PR to `Scottcjn/Rustchain`

The PR workflow:
1. Fork `Scottcjn/Rustchain`
2. Add/edit `bcos-directory/data/projects.json`
3. Open PR with your project entry
4. BCOS committee reviews and approves

---

## Building the Static Site

```bash
# Generate dist/index.html (self-contained, no server needed)
python build.py

# Output: dist/index.html (~XX KB, all data embedded)
```

The built `dist/index.html` is fully self-contained and can be hosted on:
- GitHub Pages
- Nginx / Apache
- IPFS
- Any static file server

---

## Live Deployment

**Option 1: GitHub Pages**

The `index.html` fetches from `data/projects.json` via GitHub raw CDN. Just serve the directory.

**Option 2: Build + Host Anywhere**

```bash
python build.py
# Upload dist/index.html to your host
```

**Option 3: Direct serve (development)**

```bash
python -m http.server 8000
# Open http://localhost:8000/bcos-directory/
```

---

## Categories

- 🤖 **agent-infra** — Agent infrastructure, bots, automation
- ⛓️ **blockchain** — Core protocol, DeFi, bridges
- 🎬 **video** — Video platforms, content tools
- 🖥️ **compute-rentals** — Compute rental marketplaces

---

## Data Format Reference

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique ID, format: `bcos-XXX` |
| `name` | Yes | Project display name |
| `url` | Yes | Main project URL |
| `github` | Yes | GitHub repository URL |
| `bcos_tier` | Yes | `L0`, `L1`, or `L2` |
| `category` | Yes | One of: `agent-infra`, `blockchain`, `video`, `compute-rentals` |
| `latest_attested_sha` | Yes | Latest approved commit SHA |
| `sbom_hash` | Yes | SHA256 hash of CI-built SBOM artifact |
| `review_note` | Yes | One-line human-readable description |
| `attested_at` | Yes | Date of BCOS attestation (YYYY-MM-DD) |
| `reviewer` | Yes | BCOS committee member who reviewed |
| `badges` | No | Additional badge tags, e.g. `["verified", "core"]` |

---

## License

MIT — BCOS Committee, RustChain Ecosystem
