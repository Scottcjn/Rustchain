import os
import sys
import subprocess
import shutil
import json
import tkinter as tk
from tkinter import messagebox, simpledialog
import urllib.request
import zipfile

# Configuration
APP_NAME = "RustChain Miner"
INSTALL_DIR = os.path.join(os.environ["LOCALAPPDATA"], "RustChain")
MINER_URL = "https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/linux/rustchain_linux_miner.py"
FINGERPRINT_URL = "https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/linux/fingerprint_checks.py"
PYTHON_ZIP_URL = "https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip"

def download_file(url, dest):
    print(f"Downloading {url}...")
    urllib.request.urlretrieve(url, dest)

def setup_installer():
    # 1. Create directory
    if not os.path.exists(INSTALL_DIR):
        os.makedirs(INSTALL_DIR)
    
    # 2. Get Wallet Name
    root = tk.Tk()
    root.withdraw()
    wallet_name = simpledialog.askstring("Input", "Enter your Wallet Name (e.g. MyOldMac):", parent=root)
    if not wallet_name:
        wallet_name = f"miner-{os.environ.get('COMPUTERNAME', 'win')}-{int(time.time()) % 1000}"
    
    # 3. Download/Extract Python (Embeddable)
    python_zip = os.path.join(INSTALL_DIR, "python_embed.zip")
    python_dir = os.path.join(INSTALL_DIR, "python")
    if not os.path.exists(python_dir):
        os.makedirs(python_dir)
        download_file(PYTHON_ZIP_URL, python_zip)
        with zipfile.ZipFile(python_zip, 'r') as zip_ref:
            zip_ref.extractall(python_dir)
        os.remove(python_zip)
        
        # Enable site-packages in embeddable python
        # We need to uncomment 'import site' in python310._pth
        pth_file = os.path.join(python_dir, "python310._pth")
        if os.path.exists(pth_file):
            with open(pth_file, "r") as f:
                content = f.read()
            content = content.replace("#import site", "import site")
            with open(pth_file, "w") as f:
                f.write(content)

    # 4. Download Miner files
    miner_path = os.path.join(INSTALL_DIR, "rustchain_miner.py")
    fingerprint_path = os.path.join(INSTALL_DIR, "fingerprint_checks.py")
    download_file(MINER_URL, miner_path)
    download_file(FINGERPRINT_URL, fingerprint_path)

    # 5. Install dependencies
    print("Installing dependencies...")
    # Install pip first for the embeddable python
    get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
    pip_script = os.path.join(INSTALL_DIR, "get-pip.py")
    download_file(get_pip_url, pip_script)
    subprocess.run([os.path.join(python_dir, "python.exe"), pip_script, "--no-warn-script-location"], check=True)
    os.remove(pip_script)
    
    # Install requests
    subprocess.run([os.path.join(python_dir, "python.exe"), "-m", "pip", "install", "requests"], check=True)

    # 6. Create Launch Scripts
    # Start Script (Batch)
    start_bat = os.path.join(INSTALL_DIR, "start_miner.bat")
    with open(start_bat, "w") as f:
        f.write(f'@echo off\ncd /d "%~dp0"\npython\\python.exe rustchain_miner.py --wallet {wallet_name}\npause')
    
    # Stop Script (Batch)
    stop_bat = os.path.join(INSTALL_DIR, "stop_miner.bat")
    with open(stop_bat, "w") as f:
        f.write(f'@echo off\ntaskkill /F /FI "WINDOWTITLE eq RustChain Miner*" /IM python.exe\necho Miner stopped.\npause')

    # 7. Create Scheduled Task for Auto-Start
    task_name = "RustChainMinerAutoStart"
    # Command to run hidden: use a VBS wrapper or just run the bat
    vbs_path = os.path.join(INSTALL_DIR, "run_hidden.vbs")
    with open(vbs_path, "w") as f:
        f.write(f'Set WshShell = CreateObject("WScript.Shell")\nWshShell.Run chr(34) & "{start_bat}" & chr(34), 0\nSet WshShell = Nothing')
    
    subprocess.run(['schtasks', '/Create', '/F', '/SC', 'ONLOGON', '/TN', task_name, '/TR', f'wscript.exe "{vbs_path}"'], check=True)

    # 8. Create Shortcuts
    # (Simplified for this script, in a real InnoSetup it's easier)
    # We'll just print instructions or try to create them via PowerShell
    print("Creating shortcuts...")
    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    start_menu = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", APP_NAME)
    if not os.path.exists(start_menu):
        os.makedirs(start_menu)
    
    def create_shortcut(target, name, folder):
        ps_script = f'$s=(New-Object -COM WScript.Shell).CreateShortcut("{os.path.join(folder, name)}.lnk");$s.TargetPath="{target}";$s.WorkingDirectory="{INSTALL_DIR}";$s.Save()'
        subprocess.run(["powershell", "-Command", ps_script], check=True)

    create_shortcut(start_bat, "Start RustChain Miner", start_menu)
    create_shortcut(stop_bat, "Stop RustChain Miner", start_menu)
    create_shortcut(INSTALL_DIR, "RustChain Miner Logs Folder", start_menu)
    
    # 9. Final Message
    messagebox.showinfo("Success", f"RustChain Miner installed successfully to {INSTALL_DIR}!\nWallet: {wallet_name}\n\nAuto-start on boot is enabled.")

if __name__ == "__main__":
    try:
        setup_installer()
    except Exception as e:
        messagebox.showerror("Error", f"Installation failed: {e}")
