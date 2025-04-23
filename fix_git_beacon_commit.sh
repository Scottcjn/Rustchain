#!/bin/bash

echo "📦 Staging all untracked files in rustchain-poa..."

# Change to the correct directory
cd "$(dirname "$0")"

# Add all files in these subfolders
git add ../docs/*.md
git add ../tools/*.py
git add tools/net/
git add tools/relay/
git add tools/wallet/
git add ../validator/
git add flame_beacon.py
git add *.c

echo "✅ Files staged."

# Commit
git commit -m "📡 Added FlameNet beacon, relay tools, wallet stubs, and docs"

# Push
git push origin main

echo "🚀 All changes pushed to GitHub."
