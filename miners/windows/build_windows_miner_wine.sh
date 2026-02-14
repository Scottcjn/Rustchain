#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

EMBED_ZIP="python-3.11.5-embed-win32.zip"
EMBED_URL="https://www.python.org/ftp/python/3.11.5/$EMBED_ZIP"
PYTHON_DIR="python311"
PYTHON_EXE="C:\\python311\\python.exe"

if [[ ! -d "$HOME/.wine/drive_c/$PYTHON_DIR" ]]; then
  echo "Downloading Python embeddable zip..."
  curl -fsSL "$EMBED_URL" -o "$EMBED_ZIP"
  echo "Unzipping into Wine C drive..."
  unzip -oq "$EMBED_ZIP" -d "$HOME/.wine/drive_c/$PYTHON_DIR"
fi

GET_PIP="get-pip.py"
GET_PIP_URL="https://bootstrap.pypa.io/get-pip.py"

if [[ ! -f "$GET_PIP" ]]; then
  echo "Downloading get-pip.py..."
  curl -fsSL "$GET_PIP_URL" -o "$GET_PIP"
fi

echo "Installing pip in Wine Python..."
wine "$PYTHON_EXE" "$GET_PIP" >/dev/null
wine "$PYTHON_EXE" -m pip install --upgrade pip >/dev/null

REQUIREMENTS_WIN=$(winepath -w "$ROOT_DIR/requirements-miner.txt")
echo "Installing miner requirements..."
wine "$PYTHON_EXE" -m pip install -r "$REQUIREMENTS_WIN" >/dev/null

echo "Installing PyInstaller..."
wine "$PYTHON_EXE" -m pip install pyinstaller >/dev/null

SCRIPT_WIN=$(winepath -w "$ROOT_DIR/rustchain_windows_miner.py")
DIST_DIR="$ROOT_DIR/dist"
rm -rf "$DIST_DIR"

echo "Building rustchain_windows_miner.exe with PyInstaller..."
wine "$PYTHON_EXE" -m PyInstaller --noconfirm --onefile --name rustchain_windows_miner "$SCRIPT_WIN" >/tmp/wine_pyinstaller.log

echo "Build finished; executable located at $DIST_DIR/rustchain_windows_miner.exe"
