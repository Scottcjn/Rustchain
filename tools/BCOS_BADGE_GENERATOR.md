# BCOS v2 Badge Generator

A web-based tool for generating **Beacon Certified Open Source (BCOS)** certification badges for verified repositories.

![BCOS Certified](https://img.shields.io/badge/BCOS-v2-brightgreen?style=flat)

## Features

- 🎨 **Dynamic SVG Badges** - Generate beautiful, tier-based certification badges
- 📊 **Trust Score Visualization** - Display repository trust score (0-100) on badge
- 🔗 **Verification Integration** - Optional QR codes linking to verification pages
- 📈 **Analytics Dashboard** - Track badge generation statistics
- 💾 **Persistent Storage** - SQLite database for badge tracking
- 🚀 **RESTful API** - Programmatic badge generation and verification

## Quick Start

### Installation

1. Ensure Python 3.8+ is installed
2. Install Flask dependency:

```bash
pip install flask
```

3. Run the badge generator:

```bash
cd tools
python bcos_badge_generator.py
```

The server will start at `http://localhost:5000`

### Command Line Options

```bash
python bcos_badge_generator.py --port 5000 --host 0.0.0.0 --debug
```

| Option | Default | Description |
|--------|---------|-------------|
| `--port` | 5000 | Port to run the server on |
| `--host` | 0.0.0.0 | Host to bind to |
| `--debug` | False | Enable debug mode |

## Usage

### Web Interface

1. Open `http://localhost:5000` in your browser
2. Enter your repository name (format: `owner/repo`)
3. Select BCOS tier (L0, L1, or L2)
4. Enter trust score from BCOS verification engine
5. Optionally add certificate ID and QR code
6. Click "Generate Badge"
7. Copy the Markdown, HTML, or SVG code for use in your README

### API Endpoints

#### Generate Badge

```bash
POST /api/badge/generate
Content-Type: application/json

{
  "repo_name": "Scottcjn/Rustchain",
  "tier": "L1",
  "trust_score": 75,
  "cert_id": "BCOS-12345678",  // optional
  "include_qr": true  // optional
}
```

Response:

```json
{
  "success": true,
  "cert_id": "BCOS-12345678",
  "svg": "<svg>...</svg>",
  "markdown": "[![BCOS L1 Certified](...)](...)",
  "html": "<a href=\"...\"><img src=\"...\" alt=\"...\"></a>",
  "verification_url": "https://rustchain.org/bcos/verify/BCOS-12345678"
}
```

#### Verify Certificate

```bash
GET /api/badge/verify/BCOS-12345678
```

Response:

```json
{
  "valid": true,
  "cached": false,
  "data": {
    "cert_id": "BCOS-12345678",
    "repo_name": "Scottcjn/Rustchain",
    "tier": "L1",
    "trust_score": 75,
    "reviewer": "Scott Boudreaux",
    "generated_at": "2026-03-22T12:00:00Z"
  }
}
```

#### Get Statistics

```bash
GET /api/badge/stats
```

Response:

```json
{
  "total_badges": 42,
  "by_tier": {
    "L0": 10,
    "L1": 25,
    "L2": 7
  },
  "recent_7_days": 15,
  "top_repos": [
    {"repo": "Scottcjn/Rustchain", "count": 5},
    {"repo": "example/project", "count": 3}
  ]
}
```

#### Download Badge SVG

```bash
GET /badge/BCOS-12345678.svg
```

Returns the SVG badge image for the specified certificate.

#### Health Check

```bash
GET /health
```

Response:

```json
{
  "status": "healthy",
  "service": "bcos-badge-generator",
  "version": "2.0.0",
  "timestamp": "2026-03-22T12:00:00Z"
}
```

## BCOS Tiers

### L0 - Basic (Score ≥40)

- ✅ Automated license compliance check
- ✅ Test evidence detection
- ✅ Basic security scans
- 🤖 No human review required

### L1 - Verified (Score ≥60)

- ✅ All L0 requirements
- ✅ Semgrep static analysis
- ✅ Vulnerability scan (OSV/CVE)
- ✅ SBOM generation
- ✅ Dependency freshness check
- 🤖 Agent review with evidence

### L2 - Certified (Score ≥80)

- ✅ All L1 requirements
- ✅ Human maintainer approval
- ✅ Signed attestation (Beacon key)
- ✅ Enhanced security review
- 👤 Human review required

## Badge Examples

### L0 Badge
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="140" height="24">
  <!-- Green gradient, "L0 - Basic" -->
</svg>
```

### L1 Badge
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="140" height="24">
  <!-- Purple gradient, "L1 - Verified" -->
</svg>
```

### L2 Badge
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="140" height="24">
  <!-- Pink gradient, "L2 - Certified" -->
</svg>
```

## Integration with BCOS Engine

The badge generator integrates with the BCOS v2 verification engine (`tools/bcos_engine.py`):

```python
# Run BCOS verification
from tools.bcos_engine import scan_repo

report = scan_repo(
    path='/path/to/repo',
    tier='L1',
    reviewer='Scott Boudreaux',
)

# Generate badge with results
import requests

response = requests.post('http://localhost:5000/api/badge/generate', json={
    'repo_name': report['repo_name'],
    'tier': report['tier'],
    'trust_score': report['trust_score'],
    'cert_id': report['cert_id'],
})

badge_data = response.json()
print(badge_data['markdown'])
```

## Database Schema

The badge generator uses SQLite with the following tables:

### `badges`

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| cert_id | TEXT | Certificate ID (unique) |
| repo_name | TEXT | Repository name |
| github_url | TEXT | GitHub URL |
| tier | TEXT | BCOS tier (L0/L1/L2) |
| trust_score | INTEGER | Trust score 0-100 |
| commitment | TEXT | BLAKE2b commitment |
| reviewer | TEXT | Reviewer name |
| generated_at | TIMESTAMP | Generation timestamp |
| download_count | INTEGER | Badge download count |
| verification_url | TEXT | Verification URL |
| sbom_hash | TEXT | SBOM hash |
| metadata | JSON | Additional metadata |

### `verification_cache`

Caches verification results for performance.

### `badge_analytics`

Tracks badge generation events for analytics.

## Testing

Run the test suite:

```bash
cd /private/tmp/rustchain-issue2292
python -m pytest tests/test_bcos_badge_generator.py -v
```

### Test Coverage

- ✅ Badge configuration validation
- ✅ SVG generation for all tiers
- ✅ Trust score color coding
- ✅ Database operations
- ✅ Certificate verification
- ✅ Flask API endpoints
- ✅ Edge cases and error handling

## Configuration

Customize badge appearance in `BADGE_CONFIG`:

```python
BADGE_CONFIG = {
    'tiers': {
        'L0': {
            'label': 'Basic',
            'color_start': '#555555',
            'color_end': '#4c1',
            'min_score': 40,
        },
        # ... more tiers
    },
    'width': 140,
    'height': 24,
    'font_family': 'Verdana, Geneva, sans-serif',
    'font_size': 11,
}
```

## Security Considerations

- Certificate IDs use BLAKE2b-256 for uniqueness
- Input validation on all API endpoints
- SQL injection prevention via parameterized queries
- File upload limits (16MB max)
- CORS headers for cross-origin requests

## Troubleshooting

### Flask not installed

```bash
pip install flask
```

### Database locked

```bash
rm bcos_badges.db
python bcos_badge_generator.py  # Will recreate
```

### Badge not displaying

1. Check certificate ID format: `BCOS-xxxxxxxx`
2. Verify repository name format: `owner/repo`
3. Ensure trust score is 0-100

## Related Tools

- [`tools/bcos_engine.py`](./bcos_engine.py) - BCOS v2 verification engine
- [`tools/bcos_spdx_check.py`](./bcos_spdx_check.py) - SPDX license checker
- [`bcos_directory.py`](../bcos_directory.py) - BCOS project directory

## License

MIT License - See [LICENSE](../LICENSE) for details.

## Contributing

Contributions welcome! Please read [CONTRIBUTING.md](../CONTRIBUTING.md) first.

## References

- [BCOS v2 Specification](../docs/BEACON_CERTIFIED_OPEN_SOURCE.md)
- [RustChain Documentation](https://rustchain.org)
- [Issue #2292](https://github.com/Scottcjn/Rustchain/issues/2292)

---

**BCOS — Beacon Certified Open Source**  
Part of the [RustChain](https://rustchain.org) ecosystem by [Elyan Labs](https://elyanlabs.ai)
