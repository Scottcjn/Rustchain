import os
import sys
import subprocess
import shutil
import tkinter as tk
from tkinter import messagebox, simpledialog
import zipfile
import time

# For PyInstaller bundled files
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

APP_NAME = "RustChain Miner"
INSTALL_DIR = os.path.join(os.environ["LOCALAPPDATA"], "RustChain")

def setup():
    # 1. Create directory
    if not os.path.exists(INSTALL_DIR):
        os.makedirs(INSTALL_DIR)
    
    # 2. Get Wallet Name
    root = tk.Tk()
    root.withdraw()
    wallet_name = simpledialog.askstring("RustChain Installer", "Enter your Wallet Name:", initialvalue=f"miner-{os.environ.get('COMPUTERNAME', 'win')}")
    if not wallet_name:
        wallet_name = f"miner-win-{int(time.time())}"
    
    # 3. Extract Bundled Python
    python_zip = resource_path("python-3.10.11-embed-amd64.zip")
    python_dir = os.path.join(INSTALL_DIR, "python")
    if not os.path.exists(python_dir):
        os.makedirs(python_dir)
        print("Extracting Python environment...")
        with zipfile.ZipFile(python_zip, 'r') as zip_ref:
            zip_ref.extractall(python_dir)
        
        # Enable site-packages
        pth_file = os.path.join(python_dir, "python310._pth")
        if os.path.exists(pth_file):
            with open(pth_file, "r") as f: lines = f.readlines()
            with open(pth_file, "w") as f:
                for line in lines:
                    if line.strip() == "#import site": f.write("import site\n")
                    else: f.write(line)

    # 4. Copy Miner files
    shutil.copy(resource_path("rustchain_miner.py"), os.path.join(INSTALL_DIR, "rustchain_miner.py"))
    shutil.copy(resource_path("fingerprint_checks.py"), os.path.join(INSTALL_DIR, "fingerprint_checks.py"))

    # 5. Setup dependencies
    py_exe = os.path.join(python_dir, "python.exe")
    # Check if pip is installed in our bundle, else download it
    if not os.path.exists(os.path.join(python_dir, "Scripts", "pip.exe")):
        print("Installing pip...")
        get_pip = resource_path("get-pip.py") # We should include this
        subprocess.run([py_exe, get_pip, "--no-warn-script-location"], check=True)
    
    print("Installing requests...")
    subprocess.run([py_exe, "-m", "pip", "install", "requests"], check=True)

    # 6. Create Launchers
    start_bat = os.path.join(INSTALL_DIR, "start_miner.bat")
    with open(start_bat, "w") as f:
        f.write(f'@echo off\ncd /d "%~dp0"\npython\\python.exe rustchain_miner.py --wallet {wallet_name}\npause')
    
    stop_bat = os.path.join(INSTALL_DIR, "stop_miner.bat")
    with open(stop_bat, "w") as f:
        f.write(f'@echo off\ntaskkill /F /FI "WINDOWTITLE eq RustChain Miner*" /IM python.exe 2>nul\necho Miner stopped.\npause')

    # 7. Scheduled Task (Auto-start)
    vbs_path = os.path.join(INSTALL_DIR, "run_hidden.vbs")
    with open(vbs_path, "w") as f:
        f.write(f'Set WshShell = CreateObject("WScript.Shell")\nWshShell.Run chr(34) & "{start_bat}" & chr(34), 0\nSet WshShell = Nothing')
    
    task_name = "RustChainMiner"
    subprocess.run(['schtasks', '/Create', '/F', '/SC', 'ONLOGON', '/TN', task_name, '/TR', f'wscript.exe "{vbs_path}"'], capture_output=True)

    # 8. Shortcuts
    def create_shortcut(target, name, folder):
        ps = f'$s=(New-Object -COM WScript.Shell).CreateShortcut("{os.path.join(folder, name)}.lnk");$s.TargetPath="{target}";$s.WorkingDirectory="{INSTALL_DIR}";$s.Save()'
        subprocess.run(["powershell", "-Command", ps], capture_output=True)

    start_menu = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", APP_NAME)
    os.makedirs(start_menu, exist_ok=True)
    create_shortcut(start_bat, "Start RustChain Miner", start_menu)
    create_shortcut(stop_bat, "Stop RustChain Miner", start_menu)
    create_shortcut(INSTALL_DIR, "Open Install Folder", start_menu)
    
    messagebox.showinfo("Done", "RustChain Miner installed!\nWallet: " + wallet_name)

if __name__ == "__main__":
    setup()
