#!/usr/bin/env python3
"""
RustChain Windows Miner - Debug Version
Writes all errors to a log file for troubleshooting
"""
import sys
import os
from pathlib import Path

# Create log file immediately
WALLET_DIR = Path.home() / ".rustchain"
WALLET_DIR.mkdir(exist_ok=True)
LOG_FILE = WALLET_DIR / "miner_debug.log"

def log(msg):
    """Write to both console and log file"""
    print(msg)
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(f"{msg}\n")
    except:
        pass

log("="*60)
log("RustChain Miner Debug Log")
log("="*60)
log(f"Python: {sys.version}")
log(f"Platform: {sys.platform}")
log(f"Log file: {LOG_FILE}")

try:
    log("\n[1] Testing imports...")

    log("  Importing os...")
    import os

    log("  Importing time...")
    import time

    log("  Importing json...")
    import json

    log("  Importing hashlib...")
    import hashlib

    log("  Importing platform...")
    import platform

    log("  Importing threading...")
    import threading

    log("  Importing tkinter...")
    import tkinter as tk

    log("  Importing tkinter.ttk...")
    from tkinter import ttk, messagebox, scrolledtext

    log("  Importing requests...")
    import requests

    log("  Importing datetime...")
    from datetime import datetime

    log("  Importing pathlib...")
    from pathlib import Path

    log("  ✓ All imports successful!")

    log("\n[2] Testing Tk window...")
    root = tk.Tk()
    root.title("RustChain Miner - Debug Test")
    root.geometry("400x300")

    log("  ✓ Tk window created")

    # Add simple UI
    label = tk.Label(root, text="RustChain Miner Debug Test", font=('Arial', 14, 'bold'))
    label.pack(pady=20)

    status_label = tk.Label(root, text="All systems operational!", foreground="green")
    status_label.pack(pady=10)

    log_display = tk.Text(root, height=10, width=50)
    log_display.pack(pady=10)
    log_display.insert('1.0', f"Python: {sys.version}\n")
    log_display.insert('end', f"Platform: {platform.system()} {platform.release()}\n")
    log_display.insert('end', f"Log file: {LOG_FILE}\n\n")
    log_display.insert('end', "All imports successful!\n")
    log_display.insert('end', "Tk window working!\n")
    log_display.config(state='disabled')

    close_btn = tk.Button(root, text="Close", command=root.quit)
    close_btn.pack(pady=10)

    log("  ✓ UI elements created")

    log("\n[3] Starting main loop...")
    log("  If you see a window, everything works!")
    log("  Close the window to continue...")

    root.mainloop()

    log("\n[4] Window closed successfully")
    log("="*60)
    log("SUCCESS: The miner environment is working correctly!")
    log("="*60)

except Exception as e:
    import traceback
    error_msg = f"\nERROR: {e}\n\n{traceback.format_exc()}"
    log(error_msg)

    # Try to show error in messagebox
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("RustChain Miner Error",
                           f"Error occurred!\n\n{e}\n\nCheck log file:\n{LOG_FILE}")
    except:
        pass

    input("\nPress Enter to exit...")
    sys.exit(1)

log("\nDebug test completed. Check the log file above for details.")
input("Press Enter to exit...")
