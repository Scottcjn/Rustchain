#!/usr/bin/env python3
"""RustChain Node Setup Wizard — Interactive setup for new operators."""
import os, sys, subprocess, json

def ask(prompt, default=""):
    val = input(f"{prompt} [{default}]: ").strip()
    return val or default

def main():
    print("=" * 50)
    print("  RustChain Node Setup Wizard")
    print("=" * 50)
    print()

    home = ask("Install directory", os.path.expanduser("~/.rustchain"))
    port = ask("API port", "8088")
    dash_port = ask("Dashboard port", "8099")
    wallet = ask("Wallet name", "my-miner")
    enable_monitoring = ask("Enable monitoring? (y/n)", "y").lower() == "y"

    print("\nCreating directories...")
    os.makedirs(f"{home}/data", exist_ok=True)
    os.makedirs(f"{home}/logs", exist_ok=True)
    os.makedirs(f"{home}/wallets", exist_ok=True)

    env = {
        "RUSTCHAIN_HOME": home,
        "NODE_PORT": port,
        "DASHBOARD_PORT": dash_port,
        "WALLET_NAME": wallet,
    }
    if enable_monitoring:
        env["PROMETHEUS_PORT"] = "9100"

    env_file = os.path.join(home, ".env")
    with open(env_file, "w") as f:
        for k, v in env.items():
            f.write(f"{k}={v}\n")

    print(f"\nConfiguration saved to {env_file}")
    print("\nNext steps:")
    print(f"  1. pip install clawrtc")
    print(f"  2. clawrtc wallet create")
    print(f"  3. clawrtc start")
    print(f"\nHappy mining!")

if __name__ == "__main__":
    main()
