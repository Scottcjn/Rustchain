"""
rustchainnode CLI — init, start, stop, status, config, dashboard, install-service.

Usage:
    rustchainnode init --wallet my-wallet-name [--port 8099] [--testnet]
    rustchainnode start [--wallet my-wallet] [--port 8099] [--testnet]
    rustchainnode stop
    rustchainnode status
    rustchainnode config
    rustchainnode dashboard
    rustchainnode install-service [--wallet my-wallet]

Author: NOX Ventures (noxxxxybot-sketch)
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

from .hardware import detect_cpu_info, get_optimal_config

CONFIG_DIR = Path.home() / ".rustchainnode"
CONFIG_FILE = CONFIG_DIR / "config.json"
PID_FILE = CONFIG_DIR / "node.pid"

NODE_URL = "https://50.28.86.131"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def _save_config(cfg: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def _check_health(node_url: str = NODE_URL) -> dict:
    try:
        import urllib.request
        with urllib.request.urlopen(f"{node_url}/health", timeout=5) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _check_epoch(node_url: str = NODE_URL) -> dict:
    try:
        import urllib.request
        with urllib.request.urlopen(f"{node_url}/epoch", timeout=5) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_init(args):
    """Initialize rustchainnode configuration."""
    print("🦀 RustChain Node — Initializing...")

    hw = detect_cpu_info()
    print(f"  Detected: {hw['arch']} ({hw['arch_type']}) | {hw['cpu_count']} CPUs")
    print(f"  Antiquity multiplier: {hw['antiquity_multiplier']}x")
    print(f"  Optimal threads: {hw['optimal_threads']}")

    wallet = args.wallet or input("  Wallet name: ").strip()
    port = args.port or 8099
    testnet = getattr(args, "testnet", False)

    cfg = get_optimal_config(wallet, port)
    cfg["testnet"] = testnet
    _save_config(cfg)

    # Test connectivity
    print(f"\n  Testing connectivity to {NODE_URL}...")
    health = _check_health()
    if health.get("ok"):
        print(f"  ✅ Node reachable: {health}")
    else:
        print(f"  ⚠️  Node unreachable ({health.get('error', 'unknown')}). Will retry on start.")

    print(f"\n  ✅ Config saved to {CONFIG_FILE}")
    print(f"  Wallet: {wallet} | Port: {port} | Threads: {hw['optimal_threads']}")
    print(f"\n  Next: rustchainnode start")


def cmd_start(args):
    """Start the RustChain attestation node."""
    cfg = _load_config()
    wallet = getattr(args, "wallet", None) or cfg.get("wallet")
    port = getattr(args, "port", None) or cfg.get("port", 8099)
    testnet = getattr(args, "testnet", False)

    if not wallet:
        print("❌ No wallet configured. Run: rustchainnode init --wallet <name>")
        sys.exit(1)

    hw = detect_cpu_info()
    node_url = "http://localhost:8099" if testnet else NODE_URL

    print(f"🚀 Starting RustChain node...")
    print(f"   Wallet: {wallet}")
    print(f"   Port: {port}")
    print(f"   CPU: {hw['arch']} | {hw['cpu_count']} threads")
    print(f"   Antiquity: {hw['antiquity_multiplier']}x")
    print(f"   Node URL: {node_url}")

    # Check health of remote node
    health = _check_health(node_url)
    if health.get("ok"):
        print(f"\n✅ Remote node online: {health.get('version', 'unknown')}")
    else:
        print(f"\n⚠️  Remote node: {health.get('error', 'unreachable')}")

    epoch = _check_epoch(node_url)
    if "epoch" in epoch:
        print(f"📊 Current epoch: {epoch['epoch']} | Slot: {epoch.get('slot', '?')}")

    print(f"\n✅ Node initialized for wallet '{wallet}'")
    print("   Configure systemd service: rustchainnode install-service")


def cmd_stop(args):
    """Stop a running rustchainnode daemon."""
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            import signal
            os.kill(pid, signal.SIGTERM)
            PID_FILE.unlink()
            print(f"✅ Node stopped (PID {pid})")
        except ProcessLookupError:
            print(f"⚠️  Process {pid} not found (already stopped?)")
            PID_FILE.unlink()
    else:
        print("ℹ️  No running node found")


def cmd_status(args):
    """Show node status."""
    cfg = _load_config()
    node_url = NODE_URL

    print("🔍 RustChain Node Status")
    print(f"   Config: {CONFIG_FILE}")

    if cfg:
        print(f"   Wallet: {cfg.get('wallet', 'not set')}")
        print(f"   Port: {cfg.get('port', 8099)}")
        print(f"   Arch: {cfg.get('arch_type', 'unknown')}")
        print(f"   Antiquity: {cfg.get('antiquity_multiplier', 1.0)}x")

    health = _check_health(node_url)
    if health.get("ok"):
        print(f"\n   🟢 Remote node: ONLINE")
        print(f"   Version: {health.get('version', '?')}")
    else:
        print(f"\n   🔴 Remote node: OFFLINE ({health.get('error', '?')})")

    epoch = _check_epoch(node_url)
    if "epoch" in epoch:
        print(f"   Epoch: {epoch['epoch']} | Slot: {epoch.get('slot', '?')}")


def cmd_config(args):
    """Show current configuration."""
    cfg = _load_config()
    if cfg:
        print(json.dumps(cfg, indent=2))
    else:
        print("No configuration found. Run: rustchainnode init --wallet <name>")


def cmd_dashboard(args):
    """Show TUI-style health dashboard."""
    cfg = _load_config()
    node_url = NODE_URL

    print("\n" + "=" * 60)
    print("  🦀 RustChain Node Dashboard")
    print("=" * 60)

    wallet = cfg.get("wallet", "not configured")
    print(f"  Wallet:      {wallet}")

    hw = detect_cpu_info()
    print(f"  CPU:         {hw['arch']} ({hw['arch_type']})")
    print(f"  Threads:     {hw['cpu_count']}")
    print(f"  Antiquity:   {hw['antiquity_multiplier']}x")

    health = _check_health(node_url)
    status_icon = "🟢" if health.get("ok") else "🔴"
    print(f"\n  Node Status: {status_icon} {'ONLINE' if health.get('ok') else 'OFFLINE'}")

    if health.get("ok"):
        print(f"  Version:     {health.get('version', '?')}")

    epoch = _check_epoch(node_url)
    if "epoch" in epoch:
        print(f"  Epoch:       {epoch.get('epoch', '?')}")
        print(f"  Slot:        {epoch.get('slot', '?')}")

    print("\n" + "=" * 60)


def cmd_install_service(args):
    """Install systemd (Linux) or launchd (macOS) service."""
    cfg = _load_config()
    wallet = getattr(args, "wallet", None) or cfg.get("wallet", "my-wallet")
    system = platform.system().lower()

    if system == "linux":
        _install_systemd(wallet)
    elif system == "darwin":
        _install_launchd(wallet)
    else:
        print(f"⚠️  Service installation not supported on {platform.system()}")
        print("   Start manually: rustchainnode start")


def _install_systemd(wallet: str):
    service_name = "rustchainnode"
    bin_path = subprocess.check_output(["which", "rustchainnode"], text=True).strip()

    service_content = f"""[Unit]
Description=RustChain Attestation Node
After=network.target

[Service]
Type=simple
User={os.getenv('USER', 'rustchain')}
ExecStart={bin_path} start --wallet {wallet}
Restart=on-failure
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""
    # Try user systemd first
    user_systemd = Path.home() / ".config/systemd/user"
    user_systemd.mkdir(parents=True, exist_ok=True)
    service_path = user_systemd / f"{service_name}.service"
    service_path.write_text(service_content)

    print(f"✅ systemd service written to {service_path}")
    print(f"\nEnable and start:")
    print(f"  systemctl --user daemon-reload")
    print(f"  systemctl --user enable {service_name}")
    print(f"  systemctl --user start {service_name}")
    print(f"  systemctl --user status {service_name}")


def _install_launchd(wallet: str):
    bin_path = subprocess.check_output(["which", "rustchainnode"], text=True).strip()
    plist_label = "ai.elyan.rustchainnode"
    plist_dir = Path.home() / "Library/LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_dir / f"{plist_label}.plist"

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{plist_label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{bin_path}</string>
        <string>start</string>
        <string>--wallet</string>
        <string>{wallet}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{Path.home()}/.rustchainnode/rustchainnode.log</string>
    <key>StandardErrorPath</key>
    <string>{Path.home()}/.rustchainnode/rustchainnode.err</string>
</dict>
</plist>
"""
    plist_path.write_text(plist_content)
    print(f"✅ launchd plist written to {plist_path}")
    print(f"\nLoad and start:")
    print(f"  launchctl load {plist_path}")
    print(f"  launchctl start {plist_label}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="rustchainnode",
        description="🦀 RustChain attestation node — pip installable",
    )
    subparsers = parser.add_subparsers(dest="command", help="command")

    # init
    p_init = subparsers.add_parser("init", help="Initialize node configuration")
    p_init.add_argument("--wallet", default=None, help="RTC wallet name")
    p_init.add_argument("--port", type=int, default=8099, help="Local port (default: 8099)")
    p_init.add_argument("--testnet", action="store_true", help="Use local testnet")

    # start
    p_start = subparsers.add_parser("start", help="Start the node")
    p_start.add_argument("--wallet", default=None)
    p_start.add_argument("--port", type=int, default=None)
    p_start.add_argument("--testnet", action="store_true")

    # stop
    subparsers.add_parser("stop", help="Stop running node")

    # status
    subparsers.add_parser("status", help="Show node status")

    # config
    subparsers.add_parser("config", help="Show current configuration")

    # dashboard
    subparsers.add_parser("dashboard", help="TUI health dashboard")

    # install-service
    p_svc = subparsers.add_parser("install-service", help="Install systemd/launchd service")
    p_svc.add_argument("--wallet", default=None)

    args = parser.parse_args()

    dispatch = {
        "init": cmd_init,
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "config": cmd_config,
        "dashboard": cmd_dashboard,
        "install-service": cmd_install_service,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
