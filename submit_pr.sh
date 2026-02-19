#!/bin/bash

# Submit PR for XP/Badge Automation Hardening Tests
echo "Adding files to git..."
git add .github/workflows/xp-badge-tests.yml
git add tests/
git add README.md

echo "Committing changes..."
git commit -m "feat: Add comprehensive XP/Badge automation hardening tests

- Add GitHub Actions workflow for XP/Badge automation testing
- Implement core logic tests for badge unlocking
- Add JSON schema validation for proof_of_antiquity.json and relic_rewards.json
- Include data consistency tests for badge IDs and descriptions
- Add error handling and edge case testing
- Update README with testing documentation

Fixes #312"

echo "Pushing to branch..."
git push origin xp-badge-hardening-tests

echo "PR ready to be submitted!"