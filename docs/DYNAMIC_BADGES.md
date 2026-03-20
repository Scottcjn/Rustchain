# SPDX-License-Identifier: MIT
# Dynamic Shields Badges - Copy-Paste Examples

This document provides ready-to-use examples for embedding Rustchain's dynamic shields badges in external repositories, profiles, and documentation.

## Available Badges

### Repository Summary Badge
Shows total hunters, total RTC rewards, and weekly growth.

```markdown
[![Rustchain Stats](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/repo_summary.json)](https://github.com/Scottcjn/Rustchain)
```

### Weekly Growth Badge
Displays current week's new hunters and RTC distributed.

```markdown
[![Weekly Growth](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/weekly_growth.json)](https://github.com/Scottcjn/Rustchain/issues)
```

### Top Hunters Badge
Shows the top 3 hunters by RTC earned.

```markdown
[![Top Hunters](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/top_hunters.json)](https://github.com/Scottcjn/Rustchain/graphs/contributors)
```

### Category-Specific Badges

#### Documentation Contributions
```markdown
[![Docs Contributors](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/category_docs.json)](https://github.com/Scottcjn/Rustchain/labels/documentation)
```

#### Bug Hunters
```markdown
[![Bug Hunters](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/category_bug.json)](https://github.com/Scottcjn/Rustchain/labels/bug)
```

#### Outreach Champions
```markdown
[![Outreach](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/category_outreach.json)](https://github.com/Scottcjn/Rustchain/labels/outreach)
```

## Per-Hunter Badges

Individual hunter badges are generated using safe slug patterns. Replace `{hunter-slug}` with the actual slug from the badges directory.

### Hunter Profile Badge
```markdown
[![My Rustchain Stats](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/hunter_{hunter-slug}.json)](https://github.com/Scottcjn/Rustchain)
```

### Hunter Rank Badge
```markdown
[![Rustchain Rank](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/hunter_{hunter-slug}_rank.json)](https://github.com/Scottcjn/Rustchain/leaderboard)
```

## HTML Embedding

For HTML documents or websites:

```html
<img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/repo_summary.json" alt="Rustchain Stats" />
```

## Profile README Examples

### GitHub Profile Section
```markdown
## 🦀 Rustchain Contributions

[![My Rustchain Stats](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/hunter_{your-slug}.json)](https://github.com/Scottcjn/Rustchain)
[![Weekly Growth](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/weekly_growth.json)](https://github.com/Scottcjn/Rustchain/issues)

Contributing to decentralized blockchain development through bounty hunting and community engagement.
```

### Repository Header
```markdown
# My Project

[![Build](https://github.com/username/project/workflows/CI/badge.svg)](https://github.com/username/project/actions)
[![Rustchain Contributor](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/hunter_{your-slug}.json)](https://github.com/Scottcjn/Rustchain)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Powered by Rustchain bounty rewards and community-driven development.
```

## Finding Your Hunter Slug

Your hunter slug is generated from your GitHub username using these rules:
1. Lowercase conversion
2. Replace non-alphanumeric characters with hyphens
3. Remove consecutive hyphens
4. Handle collisions with numeric suffixes

Check the `.github/badges/` directory for your specific slug, or look for files matching `hunter_{something}.json`.

## Badge Customization

You can customize the appearance by adding query parameters to the shields.io URL:

```markdown
[![Rustchain Stats](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/.github/badges/repo_summary.json&style=for-the-badge&color=orange)](https://github.com/Scottcjn/Rustchain)
```

Available styles: `plastic`, `flat`, `flat-square`, `for-the-badge`, `social`

## Badge Update Frequency

- Badges are automatically updated when the CI workflow runs
- Updates occur on push to main branch and on schedule
- JSON endpoints are served from the main branch for real-time data
- Cache headers ensure badges refresh appropriately

## Troubleshooting

### Badge Not Loading
- Verify the hunter slug matches files in `.github/badges/`
- Check that the URL is correct and publicly accessible
- Ensure JSON schema validation passes

### Outdated Badge Data
- Badges update automatically with CI runs
- Manual refresh: clear browser cache or add `?refresh=1` parameter temporarily

### Missing Hunter Badge
- New hunters appear after their first merged contribution
- Check recent CI runs for badge generation logs
- Contact maintainers if badge generation appears stuck
