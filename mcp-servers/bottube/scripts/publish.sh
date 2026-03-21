#!/usr/bin/env bash
# publish.sh - Build and publish bottube-mcp-server to npm
#
# Usage:
#   ./scripts/publish.sh [patch|minor|major]
#
# Prerequisites:
#   - npm login (npm adduser)
#   - npm whoami  # confirm logged in

set -euo pipefail

VERSION_BUMP="${1:-patch}"

echo "==> Building TypeScript..."
npm run build

echo "==> Running tests..."
npm test

echo "==> Bumping version (${VERSION_BUMP})..."
npm version "${VERSION_BUMP}"

echo "==> Publishing to npm..."
npm publish --access public

echo ""
echo "==> Published successfully!"
echo "    Run: npm install -g bottube-mcp-server"
