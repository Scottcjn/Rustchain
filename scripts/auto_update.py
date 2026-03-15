#!/usr/bin/env python3
"""RustChain Auto-Updater — Check for new releases and update automatically."""
import json, urllib.request, subprocess, os, sys

REPO = "Scottcjn/Rustchain"
INSTALL_DIR = os.environ.get("RUSTCHAIN_HOME", "/opt/rustchain")

def get_latest():
    try:
        r = urllib.request.urlopen(f"https://api.github.com/repos/{REPO}/releases/latest", timeout=10)
        return json.loads(r.read())
    except:
        r = urllib.request.urlopen(f"https://api.github.com/repos/{REPO}/commits/main", timeout=10)
        return json.loads(r.read())

def get_current():
    try:
        result = subprocess.run(["git", "-C", INSTALL_DIR, "rev-parse", "HEAD"], capture_output=True, text=True)
        return result.stdout.strip()[:7]
    except:
        return "unknown"

def update():
    current = get_current()
    latest = get_latest()
    latest_sha = latest.get("sha", latest.get("tag_name", ""))[:7]
    
    print(f"Current: {current}")
    print(f"Latest:  {latest_sha}")
    
    if current == latest_sha:
        print("Already up to date!")
        return
    
    print(f"\nUpdate available! Pulling...")
    subprocess.run(["git", "-C", INSTALL_DIR, "pull", "origin", "main"], check=True)
    
    print("Installing dependencies...")
    subprocess.run([f"{INSTALL_DIR}/venv/bin/pip", "install", "-r", f"{INSTALL_DIR}/requirements.txt", "-q"], check=True)
    
    print("Update complete! Restart the node to apply changes.")

if __name__ == "__main__":
    update()
