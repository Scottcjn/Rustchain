#!/usr/bin/env python3
"""RustChain Node Reset — Safely reset node state for fresh start."""
import os, shutil, sys
DIRS = ["~/.rustchain/data", "~/.rustchain/logs", "~/.rustchain/api-cache"]
def reset(confirm=False):
    if not confirm:
        print("WARNING: This will delete all node data!")
        print("Dirs to remove:"); [print(f"  {os.path.expanduser(d)}") for d in DIRS]
        print("\nRun with --confirm to proceed")
        return
    for d in DIRS:
        path = os.path.expanduser(d)
        if os.path.exists(path):
            shutil.rmtree(path)
            print(f"  Removed: {path}")
    print("Reset complete. Restart your node.")
if __name__ == "__main__":
    reset("--confirm" in sys.argv)
