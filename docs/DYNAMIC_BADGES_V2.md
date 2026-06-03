# Dynamic Shields Badges v2

Copy-paste badge snippets for embedding RustChain badges in your README, profile, or external repos.

## Quick Start

Add any of these to your `README.md`:

### Network Status
```markdown
![RustChain Status](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/network_status.json)
```
![RustChain Status](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/network_status.json)

### Total Bounties Paid
```markdown
![Bounties Paid](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/total_bounties.json)
```

### Weekly Growth
```markdown
![Weekly Growth](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/weekly_growth.json)
```

### Top Hunters
```markdown
![Top Hunters](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/top_hunters.json)
```

## Category Badges

```markdown
![Feature Bounties](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/category_feature.json)
```

## Per-Hunter Badge

Each hunter gets a personal badge with their rank, RTC earned, and PR count:

```markdown
![My Badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/hunter_<your-slug>.json)
```

Find your slug in `.github/badges/manifest.json`.

## Custom Styles

Shields.io supports style overrides via query params:

```markdown
<!-- Flat (default) -->
![Badge](https://img.shields.io/endpoint?url=...&style=flat)

<!-- Flat Square -->
![Badge](https://img.shields.io/endpoint?url=...&style=flat-square)

<!-- For The Badge -->
![Badge](https://img.shields.io/endpoint?url=...&style=for-the-badge)

<!-- Plastic -->
![Badge](https://img.shields.io/endpoint?url=...&style=plastic)
```

## Generating Badges

```bash
# Generate all badges (run from repo root)
python .github/scripts/generate_dynamic_badges.py

# Custom data source
python .github/scripts/generate_dynamic_badges.py --data-file bounty_data.json

# Validate existing badges
python .github/scripts/generate_dynamic_badges.py --validate-only

# Run tests
python -m pytest .github/scripts/test_generate_badges.py -v
```

## Badge Schema

All badges follow the [shields.io endpoint schema](https://shields.io/badges/endpoint-badge):

```json
{
  "schemaVersion": 1,
  "label": "Label text",
  "message": "Value text",
  "color": "brightgreen",
  "style": "flat-square"
}
```

## Bounty

Closes https://github.com/Scottcjn/rustchain-bounties/issues/310
