#!/usr/bin/env python3
"""
Minimal RustChain Miner Test - Debug Version
"""
import sys
import traceback

print("=" * 60)
print("RustChain Miner Diagnostic Test")
print("=" * 60)

try:
    print("\n[1/10] Testing Python version...")
    print(f"Python: {sys.version}")

    print("\n[2/10] Testing imports...")
    import os
    print("  ✓ os")
    import time
    print("  ✓ time")
    import json
    print("  ✓ json")
    import hashlib
    print("  ✓ hashlib")
    import platform
    print("  ✓ platform")
    import threading
    print("  ✓ threading")

    print("\n[3/10] Testing tkinter...")
    import tkinter as tk
    print("  ✓ tkinter")
    from tkinter import ttk, messagebox
    print("  ✓ tkinter.ttk")
    print("  ✓ tkinter.messagebox")

    print("\n[4/10] Testing requests...")
    import requests
    print("  ✓ requests")

    print("\n[5/10] Testing pathlib...")
    from pathlib import Path
    print("  ✓ pathlib")

    print("\n[6/10] Testing Tk window creation...")
    root = tk.Tk()
    root.title("Test Window")
    root.geometry("400x200")
    print("  ✓ Tk window created")

    print("\n[7/10] Testing Label widget...")
    label = tk.Label(root, text="If you see this, GUI works!")
    label.pack(pady=20)
    print("  ✓ Label created")

    print("\n[8/10] Testing Entry widget (readonly bug check)...")
    entry = tk.Entry(root, width=40)
    entry.insert(0, "Test text")
    entry.config(state='readonly')  # This is the fix
    entry.pack(pady=10)
    print("  ✓ Entry widget works correctly")

    print("\n[9/10] Testing Button widget...")
    def on_click():
        messagebox.showinfo("Success", "All tests passed!\n\nThe miner should work.")
        root.quit()

    button = tk.Button(root, text="Click if you see this", command=on_click)
    button.pack(pady=10)
    print("  ✓ Button created")

    print("\n[10/10] Starting GUI...")
    print("\n" + "=" * 60)
    print("SUCCESS: All imports and widgets work!")
    print("A window should appear now.")
    print("If the window appears, the miner SHOULD work.")
    print("=" * 60)

    root.mainloop()

except Exception as e:
    error_msg = f"\n{'=' * 60}\nERROR FOUND:\n{e}\n\n{traceback.format_exc()}\n{'=' * 60}"
    print(error_msg)

    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Miner Test Failed", error_msg)
    except:
        pass

    input("\nPress Enter to exit...")
