# Dependabot Configuration Guide

**Issue:** #1613  
**Last Updated:** 2026-03-11

## Overview

RustChain uses GitHub Dependabot to automate dependency updates across multiple ecosystems. This document outlines the configuration, update policy, and operational guidelines.

## Configuration File

Dependabot is configured via `.github/dependabot.yml`. The configuration covers:

| Ecosystem | Directories | Schedule | PR Limit |
|-----------|-------------|----------|----------|
| pip (Python) | `/`, `/tests`, `/sdk/python`, `/integrations/mcp-server`, `/rustchainnode` | Weekly (Monday 06:00 UTC) | 2-5 per directory |
| cargo (Rust) | `/rustchain-wallet`, `/rips` | Weekly (Tuesday 06:00 UTC) | 2-3 per directory |
| npm (Node.js) | `/contracts/erc20`, `/onboard`, `/react-native-wallet`, `/snap`, `/solana` | Weekly (Wednesday 06:00 UTC) | 2-3 per directory |
| github-actions | `/` | Weekly (Thursday 06:00 UTC) | 5 |

## Update Groups

Dependencies are grouped to reduce PR noise:

### Python (pip)
- **python-security**: All security updates (priority)
- **python-dev-dependencies**: Minor and patch version updates

### Rust (cargo)
- **rust-security**: All security updates (priority)
- **rust-minor-patch**: Minor and patch version updates

### npm
- **npm-security**: All security updates (priority)
- **npm-production**: Production dependencies (minor/patch)
- **npm-development**: Development dependencies (minor/patch)

### GitHub Actions
- **github-actions**: All action version updates

## Update Policy

### Priority Levels

| Priority | Type | Action Required |
|----------|------|-----------------|
| **Critical** | Security updates with known CVEs | Review and merge within 48 hours |
| **High** | Security updates (no active exploit) | Review and merge within 7 days |
| **Medium** | Minor version updates | Review within 14 days |
| **Low** | Patch version updates | Review within 30 days |

### Review Guidelines

1. **Security Updates**: Always prioritize. Check linked CVE details.
2. **Breaking Changes**: Review changelogs for major version updates.
3. **Test Coverage**: Ensure CI passes before merging.
4. **Dependency Chains**: Watch for cascading updates.

### Merge Policy

- **Automerge**: Patch updates with passing CI may be auto-merged (if enabled)
- **Manual Review**: Minor/major updates require maintainer approval
- **Blocked PRs**: Add `dependencies blocked` label if update causes issues

## Adding New Directories

To add Dependabot coverage for a new directory:

1. Ensure the directory contains a valid manifest file:
   - Python: `requirements.txt` or `pyproject.toml`
   - Rust: `Cargo.toml`
   - Node.js: `package.json`

2. Add a new entry to `.github/dependabot.yml`:

```yaml
- package-ecosystem: "pip"  # or "cargo", "npm"
  directory: "/path/to/directory"
  schedule:
    interval: "weekly"
    day: "monday"
    time: "06:00"
    timezone: "UTC"
  open-pull-requests-limit: 3
```

3. Test configuration with Dependabot preview (if available)

## Troubleshooting

### Dependabot Not Creating PRs

- Check `open-pull-requests-limit` - may be at capacity
- Verify manifest file is valid and parseable
- Ensure directory path is correct (must be absolute from repo root)

### PRs Failing CI

- Review changelog for breaking changes
- Check if dependency requires lockfile update
- Test locally before merging

### Ignoring Specific Dependencies

Add an `ignore` block to skip specific dependencies:

```yaml
- package-ecosystem: "pip"
  directory: "/"
  ignore:
    - dependency-name: "package-name"
      versions: ["1.x", "2.x"]
```

### Custom Version Updates

To update only specific version ranges:

```yaml
- package-ecosystem: "npm"
  directory: "/"
  groups:
    stable-updates:
      patterns:
        - "*"
      update-types:
        - "patch"
```

## Security Considerations

1. **Supply Chain**: Dependabot helps mitigate supply chain risks by keeping dependencies current
2. **CVE Monitoring**: Security updates are prioritized and grouped separately
3. **Review Required**: All updates should be reviewed before merging to production

## Related Documentation

- [GitHub Dependabot Docs](https://docs.github.com/en/code-security/dependabot)
- [SECURITY.md](./SECURITY.md) - Security policy and reporting
- [CONTRIBUTING.md](./CONTRIBUTING.md) - Contribution guidelines

## Maintenance

This configuration should be reviewed quarterly to:
- Add new directories as the project grows
- Adjust schedules based on team capacity
- Update groupings based on PR volume

## Contact

For questions about dependency management or Dependabot configuration, open a GitHub issue or contact the maintainers.
