#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
RELEASE_DIR="$ROOT/release/windows_miner_release"
ZIP_PATH="$ROOT/release/rustchain_windows_miner_release.zip"
EXE_PATH="$ROOT/dist/rustchain_windows_miner.exe"

if [[ ! -f "$EXE_PATH" ]]; then
  echo "ERROR: $EXE_PATH missing. Run build_windows_miner_wine.sh first."
  exit 1
fi

rm -rf "$ROOT/release"
mkdir -p "$RELEASE_DIR"

cp "$EXE_PATH" "$RELEASE_DIR/"
cp "$ROOT/rustchain_miner_setup.bat" "$RELEASE_DIR/"
cp "$ROOT/requirements-miner.txt" "$RELEASE_DIR/"

cat <<'EOF' > "$RELEASE_DIR/README.txt"
RustChain Windows Miner release

- Run `rustchain_miner_setup.bat` to install Python + dependencies (requests, PyInstaller, etc.).
- The installer outputs `rustchain_windows_miner.exe`, which is included below.
- Use the bat file to keep the miner running (make a shortcut or scheduled task).
- The `requirements-miner.txt` file lists runtime dependencies in case you rebuild manually.
EOF

zip -r "$ZIP_PATH" -j "$RELEASE_DIR"/*

echo "Release package is ready: $ZIP_PATH"
