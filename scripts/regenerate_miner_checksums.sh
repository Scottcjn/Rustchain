#!/usr/bin/env bash
# Regenerate miners/checksums.sha256 from the artifacts it already tracks.
# Run this after editing any pinned miner file (or let the pre-commit hook do it).
# The tracked artifact list is derived from the manifest itself, so it never
# drifts from what tests/test_install_miner_checksums.py verifies.
set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/miners"
[ -f checksums.sha256 ] || { echo "no miners/checksums.sha256 found" >&2; exit 1; }
tmp="$(mktemp)"
# Preserve order + the exact tracked set; recompute each digest.
while read -r _ artifact; do
  [ -n "${artifact:-}" ] || continue
  sha256sum "$artifact"
done < checksums.sha256 > "$tmp"
mv "$tmp" checksums.sha256
echo "Regenerated miners/checksums.sha256 ($(wc -l < checksums.sha256) artifacts)"
