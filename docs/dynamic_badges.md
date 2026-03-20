# SPDX-License-Identifier: MIT

# Dynamic Shields Badges Documentation

This documentation covers the comprehensive dynamic badge system for Rustchain, including usage examples, technical implementation details, and embed code snippets for external repositories and GitHub profiles.

## Overview

The Rustchain dynamic badge system generates real-time shields.io compatible badges that display live metrics about bounty hunters, project statistics, and contribution data. All badges are automatically updated through our CI pipeline and served as JSON endpoints.

## Available Badge Types

### Core Metrics Badges

#### Total Bounty Pool
```markdown
![Total Bounty Pool](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/total_bounty_pool.json)
```

#### Active Hunters
```markdown
![Active Hunters](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/active_hunters.json)
```

#### Completed Bounties
```markdown
![Completed Bounties](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/completed_bounties.json)
```

### Growth Metrics

#### Weekly Growth
```markdown
![Weekly Growth](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/weekly_growth.json)
```

#### Monthly Active Contributors
```markdown
![Monthly Contributors](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/monthly_contributors.json)
```

### Top Performers

#### Top Hunter Badge
```markdown
![Top Hunter](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/top_hunter.json)
```

#### Top 3 Hunters Summary
```markdown
![Top 3 Hunters](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/top_3_hunters.json)
```

### Category-Specific Badges

#### Documentation Contributions
```markdown
![Docs Contributions](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/docs_contributions.json)
```

#### Bug Fixes
```markdown
![Bug Fixes](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/bug_fixes.json)
```

#### Outreach & Marketing
```markdown
![Outreach](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/outreach_contributions.json)
```

## Per-Hunter Individual Badges

### Usage Pattern
Each hunter gets a personalized badge with collision-safe slug generation:

```markdown
![Hunter Stats](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/hunters/hunter_[SLUG].json)
```

### Examples for Real Hunters
```markdown
![alice_dev Stats](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/hunters/hunter_alice_dev.json)

![bob_crypto Stats](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/hunters/hunter_bob_crypto.json)

![charlie_rs Stats](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/hunters/hunter_charlie_rs.json)
```

## HTML Embed Examples

For websites and documentation that support HTML:

```html
<!-- Total Bounty Pool -->
<img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/total_bounty_pool.json" alt="Total Bounty Pool">

<!-- Active Hunters with Link -->
<a href="https://github.com/Scottcjn/Rustchain/issues?q=is%3Aissue+label%3Abounty">
  <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/active_hunters.json" alt="Active Hunters">
</a>

<!-- Weekly Growth -->
<img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/weekly_growth.json" alt="Weekly Growth">
```

## GitHub Profile README Usage

Perfect for personal GitHub profiles showcasing your Rustchain contributions:

```markdown
## 🏆 Rustchain Contributions

![My Rustchain Stats](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/hunters/hunter_[YOUR_SLUG].json)

### Project Overview
![Total Pool](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/total_bounty_pool.json)
![Active Hunters](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/active_hunters.json)
![Weekly Growth](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/weekly_growth.json)
```

## External Repository Integration

### For Project READMEs
```markdown
## Built with Rustchain Support

This project is supported by the Rustchain bounty ecosystem:

[![Rustchain Bounties](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/total_bounty_pool.json)](https://github.com/Scottcjn/Rustchain)
[![Active Contributors](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/active_hunters.json)](https://github.com/Scottcjn/Rustchain/issues?q=is%3Aissue+label%3Abounty)
```

### For Documentation Sites
```markdown
### Community Stats

The Rustchain community is growing rapidly:

- ![Weekly Growth](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/weekly_growth.json) new contributors this week
- ![Top Hunter](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/top_hunter.json) leading contributor
- ![Bug Fixes](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/bug_fixes.json) resolved this month
```

## Badge JSON Schema

All badges follow the shields.io endpoint JSON schema:

```json
{
  "schemaVersion": 1,
  "label": "bounty pool",
  "message": "1,247 RTC",
  "color": "brightgreen",
  "cacheSeconds": 300
}
```

### Schema Fields

- **schemaVersion**: Always `1` (shields.io requirement)
- **label**: Left side text of the badge
- **message**: Right side text (the dynamic value)
- **color**: Badge color (`brightgreen`, `green`, `yellow`, `orange`, `red`, `blue`, `lightgrey`)
- **cacheSeconds**: How long shields.io should cache the badge (300 = 5 minutes)

## Color Coding System

Our badges use consistent color coding based on data significance:

- **brightgreen**: Excellent metrics (high bounty pools, top performers)
- **green**: Good metrics (steady growth, active contributors)
- **yellow**: Moderate metrics (average performance)
- **orange**: Attention needed (declining metrics)
- **red**: Critical metrics (low activity, issues)
- **blue**: Informational badges (categories, labels)
- **lightgrey**: Neutral or unavailable data

## Technical Implementation

### Badge Generation Pipeline

1. **Data Collection**: CI workflow extracts metrics from issues, PRs, and bounty data
2. **Slug Generation**: Collision-safe slugs using MD5 hash fallback for conflicts
3. **JSON Generation**: Creates shields.io compatible JSON files
4. **Validation**: Schema validation ensures all badges meet requirements
5. **Commit**: Only changed badge files are committed to reduce repo noise

### File Structure
```
.github/
├── badges/
│   ├── total_bounty_pool.json
│   ├── active_hunters.json
│   ├── weekly_growth.json
│   ├── top_3_hunters.json
│   └── hunters/
│       ├── hunter_alice_dev.json
│       ├── hunter_bob_crypto.json
│       └── hunter_[slug].json
└── scripts/
    └── generate_dynamic_badges.py
```

### Slug Generation Algorithm

Hunter slugs are generated using this collision-safe approach:

1. Convert GitHub username to lowercase
2. Replace non-alphanumeric chars with underscores
3. Truncate to 20 characters maximum
4. Check for existing conflicts
5. If conflict exists, append MD5 hash suffix
6. Final format: `hunter_[clean_slug]` or `hunter_[clean_slug]_[hash8]`

## Customization Options

### Custom Colors
You can override badge colors by adding query parameters:

```markdown
![Custom Color](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/total_bounty_pool.json&color=purple)
```

### Custom Labels
Override the left-side label:

```markdown
![Custom Label](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/active_hunters.json&label=Contributors)
```

### Custom Styling
Apply shields.io styling options:

```markdown
![Flat Style](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/weekly_growth.json&style=flat)

![For the Badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/top_hunter.json&style=for-the-badge)
```

## Update Frequency

Badges are automatically updated:
- **On every push** to main branch
- **Daily at 00:00 UTC** via scheduled workflow
- **On demand** via manual workflow dispatch

Cache duration is set to 5 minutes, so external displays will refresh relatively quickly after updates.

## Troubleshooting

### Badge Not Displaying
1. Verify the JSON file exists in the repository
2. Check that the URL is correctly formatted
3. Ensure the JSON schema is valid
4. Try bypassing cache with `?v=timestamp` parameter

### Outdated Data
1. Check the last commit time on badge files
2. Force refresh by appending `?v=[current_timestamp]`
3. Verify CI pipeline is running successfully

### Custom Hunter Badge Missing
1. Ensure you have at least one bounty interaction
2. Check if your username generates a valid slug
3. Look for your badge in the `hunters/` directory
4. Contact maintainers if your badge should exist but doesn't

## API Rate Limits

The badge generation system respects GitHub API rate limits by:
- Using authenticated requests when available
- Implementing exponential backoff on rate limit hits
- Caching data between runs when possible
- Batching API requests efficiently

## Contributing

To contribute new badge types or improvements:

1. Fork the repository
2. Modify `.github/scripts/generate_dynamic_badges.py`
3. Add validation tests for your new badges
4. Ensure CI passes with your changes
5. Submit a pull request with examples in your description

For questions or support, please open an issue with the `badge` label.
