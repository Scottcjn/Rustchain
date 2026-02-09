import os
import sys
import subprocess
import threading
import time
import webbrowser
import json
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item
import tkinter as tk
from tkinter import messagebox

# Helper for bundled files
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# Configuration
INSTALL_DIR = os.path.expanduser("~/.rustchain")
MINER_SCRIPT = resource_path("rustchain_miner.py")
LOG_FILE = os.path.join(INSTALL_DIR, "miner.log")
WALLET_FILE = os.path.join(INSTALL_DIR, "wallet.txt")

class MinerTrayApp:
    def __init__(self):
        self.process = None
        self.status = "Stopped"
        self.icon = None
        self.wallet_name = self.load_wallet()
        os.makedirs(INSTALL_DIR, exist_ok=True)

    def load_wallet(self):
        if os.path.exists(WALLET_FILE):
            with open(WALLET_FILE, "r") as f:
                return f.read().strip()
        return "default-miner"

    def create_image(self, color):
        image = Image.new('RGB', (64, 64), (255, 255, 255))
        dc = ImageDraw.Draw(image)
        dc.ellipse((10, 10, 54, 54), fill=color, outline="black")
        return image

    def get_status_color(self):
        if self.status == "Mining":
            return "green"
        elif self.status == "Error":
            return "red"
        else:
            return "gray"

    def update_icon(self):
        if self.icon:
            self.icon.icon = self.create_image(self.get_status_color())
            self.icon.title = f"RustChain Miner - {self.status}"

    def start_miner(self):
        if self.status == "Mining":
            return
        
        # Check if venv exists
        venv_python = os.path.join(INSTALL_DIR, "venv", "Scripts", "python.exe")
        if not os.path.exists(venv_python):
            # Fallback to system python if venv not found
            venv_python = sys.executable

        def run():
            try:
                self.status = "Mining"
                self.update_icon()
                self.process = subprocess.Popen(
                    [venv_python, MINER_SCRIPT, "--wallet", self.wallet_name],
                    stdout=open(LOG_FILE, "a"),
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                self.process.wait()
                if self.process and self.process.returncode != 0:
                    self.status = "Error"
                else:
                    self.status = "Stopped"
            except Exception as e:
                self.status = "Error"
            finally:
                self.update_icon()

        threading.Thread(target=run, daemon=True).start()

    def stop_miner(self):
        if self.process:
            self.process.terminate()
            self.process = None
        self.status = "Stopped"
        self.update_icon()

    def view_logs(self):
        if os.path.exists(LOG_FILE):
            if sys.platform == "win32":
                os.startfile(LOG_FILE)
            else:
                subprocess.run(["xdg-open", LOG_FILE])

    def open_status(self):
        webbrowser.open("https://50.28.86.131/api/miners")

    def quit_app(self, icon):
        self.stop_miner()
        icon.stop()

    def setup_menu(self):
        return (
            item(f'Status: {self.status}', lambda: None, enabled=False),
            item(f'Wallet: {self.wallet_name}', lambda: None, enabled=False),
            item('Start Miner', self.start_miner),
            item('Stop Miner', self.stop_miner),
            item('View Logs', self.view_logs),
            item('Network Status', self.open_status),
            item('Exit', self.quit_app),
        )

    def run(self):
        self.icon = pystray.Icon(
            "RustChain Miner",
            self.create_image(self.get_status_color()),
            "RustChain Miner",
            self.setup_menu()
        )
        
        threading.Thread(target=self.status_monitor, daemon=True).start()
        
        # Auto-start miner if wallet is configured
        if self.wallet_name != "default-miner":
            self.start_miner()
            
        self.icon.run()

    def status_monitor(self):
        while True:
            if self.process and self.process.poll() is not None:
                if self.process.returncode != 0:
                    self.status = "Error"
                else:
                    self.status = "Stopped"
                self.process = None
                self.update_icon()
            
            # Refresh menu to update status text
            if self.icon:
                self.icon.menu = pystray.Menu(*self.setup_menu())
                
            time.sleep(5)

if __name__ == "__main__":
    app = MinerTrayApp()
    app.run()

if __name__ == "__main__":
    app = MinerTrayApp()
    app.run()
