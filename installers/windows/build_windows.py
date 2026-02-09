import os
import subprocess
import urllib.request

# Configuration
REPO_BASE_LINUX = "https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/linux/"
REPO_BASE_WINDOWS = "https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/windows/"
FILES = [
    (REPO_BASE_WINDOWS + "rustchain_windows_miner.py", "rustchain_miner.py"),
    (REPO_BASE_LINUX + "fingerprint_checks.py", "fingerprint_checks.py")
]

def download_files():
    print("Downloading miner files...")
    for url, local in FILES:
        print(f"  {url} -> {local}")
        urllib.request.urlretrieve(url, local)

def build_exe():
    print("Building tray_app.exe with PyInstaller...")
    subprocess.run([
        "pyinstaller",
        "--onefile",
        "--noconsole",
        "--add-data", "rustchain_miner.py;.",
        "--add-data", "fingerprint_checks.py;.",
        "src/tray_app.py"
    ], check=True)

if __name__ == "__main__":
    download_files()
    # Note: Building needs PyInstaller and NSIS installed on a Windows host
    # build_exe()
    print("Code prepared. To build, run on Windows with PyInstaller and NSIS.")
