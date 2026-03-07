#!/usr/bin/env python3
"""
ClawRTC - RustChain Miner Setup Wizard

One-command miner setup: curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/setup.sh | bash

Or: pip install clawrtc && clawrtc setup

Usage:
    clawrtc setup          # Interactive setup wizard
    clawrtc start         # Start mining
    clawrtc status        # Check mining status
    clawrtc stop          # Stop mining
    clawrtc logs          # View miner logs
    clawrtc health        # Run health check
"""

import argparse
import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

# Configuration
VERSION = "1.0.0"
DEFAULT_NODE_URL = "https://50.28.86.131"
BACKUP_NODE_URL = "https://50.28.86.153"
INSTALL_DIR = Path.home() / ".clawrtc"
MINER_DIR = INSTALL_DIR / "miner"
VENV_DIR = INSTALL_DIR / "venv"
CONFIG_FILE = INSTALL_DIR / "config.json"
SERVICE_NAME = "clawrtc-miner"

# Colors
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
CYAN = '\033[0;36m'
NC = '\033[0m'  # No Color


def log_info(msg: str):
    print(f"{CYAN}[*]{NC} {msg}")


def log_success(msg: str):
    print(f"{GREEN}[✓]{NC} {msg}")


def log_warn(msg: str):
    print(f"{YELLOW}[!] {NC}{msg}")


def log_error(msg: str):
    print(f"{RED}[✗]{NC} {msg}")


def get_platform() -> Tuple[str, str]:
    """Detect platform and architecture"""
    import platform
    os_name = platform.system().lower()
    arch = platform.machine().lower()
    
    if os_name == "linux":
        if arch in ["aarch64", "arm64"]:
            return "linux", "aarch64"
        elif arch in ["x86_64", "amd64"]:
            return "linux", "x86_64"
        elif arch in ["ppc64le", "powerpc64le"]:
            return "linux", "ppc64le"
        elif arch in ["ppc64", "powerpc64"]:
            return "linux", "ppc64"
    elif os_name == "darwin":
        if arch in ["arm64", "aarch64"]:
            return "macos", "arm64"
        else:
            return "macos", "x86_64"
    
    return "unknown", arch


def detect_hardware() -> Dict[str, Any]:
    """Detect hardware information"""
    import platform
    import multiprocessing
    import psutil
    
    os_name, arch = get_platform()
    
    info = {
        "os": os_name,
        "arch": arch,
        "cpu_cores": multiprocessing.cpu_count(),
        "cpu_physical": psutil.cpu_count(logical=False) or multiprocessing.cpu_count(),
        "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "cpu_model": platform.processor() or "unknown",
    }
    
    # Calculate recommended threads (leave 2 cores for system)
    info["recommended_threads"] = max(1, info["cpu_physical"] - 2)
    
    # Calculate antiquity multiplier based on architecture
    # Vintage CPUs get bonus
    vintage_archs = ["powerpc", "ppc", "g5", "g4", "g3", "604", "750", "7400"]
    if any(v in arch.lower() for v in vintage_archs):
        info["antiquity_multiplier"] = 2.5
        info["is_vintage"] = True
    elif arch in ["aarch64", "arm64"]:
        info["antiquity_multiplier"] = 1.0
        info["is_vintage"] = False
    else:
        info["antiquity_multiplier"] = 1.0
        info["is_vintage"] = False
    
    return info


def check_python_version() -> bool:
    """Check if Python 3.8+ is available"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        log_error(f"Python 3.8+ required. Found Python {version.major}.{version.minor}")
        return False
    log_success(f"Python {version.major}.{version.minor}.{version.micro} detected")
    return True


def check_node_connectivity(node_url: str) -> bool:
    """Check if node is reachable"""
    try:
        req = urllib.request.Request(
            f"{node_url}/health",
            headers={'Accept': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            log_success(f"Node connected: {data.get('version', 'unknown version')}")
            return True
    except Exception as e:
        log_error(f"Cannot connect to node: {e}")
        return False


def download_miner_files() -> bool:
    """Download miner files from GitHub"""
    log_info("Downloading miner files...")
    
    MINER_FILES = [
        ("rustchain_linux_miner.py", "miners/linux/"),
        ("fingerprint_checks.py", "node/"),
    ]
    
    os.makedirs(MINER_DIR, exist_ok=True)
    
    base_url = "https://raw.githubusercontent.com/Scottcjn/Rustchain/main"
    
    for filename, path in MINER_FILES:
        url = f"{base_url}/{path}{filename}"
        dest = MINER_DIR / filename
        
        try:
            log_info(f"Downloading {filename}...")
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read()
                with open(dest, 'wb') as f:
                    f.write(content)
            log_success(f"Downloaded {filename}")
        except Exception as e:
            log_error(f"Failed to download {filename}: {e}")
            return False
    
    return True


def create_virtual_environment() -> bool:
    """Create Python virtual environment"""
    log_info("Creating virtual environment...")
    
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            check=True,
            capture_output=True
        )
        log_success("Virtual environment created")
        
        # Install dependencies
        pip = VENV_DIR / "bin" / "pip"
        log_info("Installing dependencies...")
        
        subprocess.run(
            [str(pip), "install", "--quiet", "requests", "psutil", "ecdsa"],
            check=True,
            capture_output=True
        )
        log_success("Dependencies installed")
        
        return True
    except Exception as e:
        log_error(f"Failed to create venv: {e}")
        return False


def setup_wallet() -> str:
    """Interactive wallet setup"""
    log_info("Setting up wallet...")
    
    wallet_name = input(f"{CYAN}Enter wallet name (or press Enter for random): {NC}").strip()
    
    if not wallet_name:
        import uuid
        wallet_name = f"miner_{uuid.uuid4().hex[:8]}"
        log_info(f"Generated wallet name: {wallet_name}")
    
    # Save wallet name to config
    config = load_config()
    config["wallet_name"] = wallet_name
    save_config(config)
    
    log_success(f"Wallet '{wallet_name}' configured")
    return wallet_name


def run_fingerprint_check() -> bool:
    """Run fingerprint checks"""
    log_info("Running fingerprint checks...")
    
    miner_file = MINER_DIR / "rustchain_linux_miner.py"
    
    if not miner_file.exists():
        log_error("Miner file not found. Run setup first.")
        return False
    
    try:
        python = VENV_DIR / "bin" / "python"
        
        # Import and run fingerprint checks
        sys.path.insert(0, str(MINER_DIR))
        from fingerprint_checks import run_all_checks
        
        results = run_all_checks()
        
        passed = sum(1 for r in results if r.get("passed", False))
        total = len(results)
        
        log_info(f"Fingerprint checks: {passed}/{total} passed")
        
        for r in results:
            status = "✓" if r.get("passed") else "✗"
            log_info(f"  {status} {r.get('name', 'unknown')}: {r.get('message', '')}")
        
        return passed == total
    except Exception as e:
        log_warn(f"Fingerprint check error: {e}")
        return False


def install_service() -> bool:
    """Install systemd/launchd service"""
    log_info("Installing service...")
    
    os_name, _ = get_platform()
    
    config = load_config()
    wallet_name = config.get("wallet_name", "default")
    
    if os_name == "linux":
        service_file = Path.home() / ".config" / "systemd" / "user" / f"{SERVICE_NAME}.service"
        service_file.parent.mkdir(parents=True, exist_ok=True)
        
        python_path = VENV_DIR / "bin" / "python"
        miner_path = MINER_DIR / "rustchain_linux_miner.py"
        
        content = f"""[Unit]
Description=ClawRTC RustChain Miner
After=network.target

[Service]
Type=simple
WorkingDirectory={MINER_DIR}
ExecStart={python_path} {miner_path} --wallet {wallet_name} --node {DEFAULT_NODE_URL}
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
"""
        
        with open(service_file, 'w') as f:
            f.write(content)
        
        log_success(f"Service installed to {service_file}")
        log_info("Run 'systemctl --user start clawrtc-miner' to start")
        
    elif os_name == "macos":
        plist_file = Path.home() / "Library" / "LaunchAgents" / f"com.rustchain.miner.plist"
        plist_file.parent.mkdir(parents=True, exist_ok=True)
        
        python_path = VENV_DIR / "bin" / "python"
        miner_path = MINER_DIR / "rustchain_linux_miner.py"
        
        content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.rustchain.miner</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{miner_path}</string>
        <string>--wallet</string>
        <string>{wallet_name}</string>
        <string>--node</string>
        <string>{DEFAULT_NODE_URL}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
"""
        
        with open(plist_file, 'w') as f:
            f.write(content)
        
        log_success(f"Service installed to {plist_file}")
        log_info("Run 'launchctl load ~/Library/LaunchAgents/com.rustchain.miner.plist' to start")
    else:
        log_warn("Service installation not supported on this platform")
        return False
    
    return True


def load_config() -> Dict[str, Any]:
    """Load configuration"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(config: Dict[str, Any]):
    """Save configuration"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def check_health() -> bool:
    """Check miner health"""
    config = load_config()
    wallet = config.get("wallet_name", "unknown")
    
    log_info(f"Checking health for wallet: {wallet}")
    
    # Try primary node
    for node_url in [DEFAULT_NODE_URL, BACKUP_NODE_URL]:
        try:
            req = urllib.request.Request(
                f"{node_url}/health",
                headers={'Accept': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                log_success(f"Node healthy: {data.get('version', 'unknown')}")
                log_info(f"  Epoch: {data.get('current_epoch', 'N/A')}")
                log_info(f"  Uptime: {data.get('uptime_s', 0)}s")
                return True
        except Exception as e:
            continue
    
    log_error("Node not reachable")
    return False


def cmd_setup(args):
    """Run setup wizard"""
    print(f"{CYAN}ClawRTC Miner Setup Wizard v{VERSION}{NC}")
    print("=" * 50)
    
    # Step 1: Platform detection
    log_info("Step 1: Detecting platform...")
    os_name, arch = get_platform()
    log_success(f"Platform: {os_name} ({arch})")
    
    # Step 2: Hardware detection
    log_info("Step 2: Detecting hardware...")
    hw = detect_hardware()
    log_success(f"CPU: {hw['cpu_model']}")
    log_success(f"Cores: {hw['cpu_physical']} physical, {hw['cpu_cores']} logical")
    log_success(f"RAM: {hw['ram_total_gb']} GB")
    log_success(f"Recommended threads: {hw['recommended_threads']}")
    log_success(f"Antiquity multiplier: {hw['antiquity_multiplier']}x")
    if hw.get('is_vintage'):
        log_success("Vintage CPU detected! You're eligible for 2.5x rewards!")
    
    # Step 3: Python check
    log_info("Step 3: Checking Python...")
    if not check_python_version():
        return 1
    
    # Step 4: Node connectivity
    log_info("Step 4: Checking node connectivity...")
    if not check_node_connectivity(DEFAULT_NODE_URL):
        log_warn("Primary node unreachable, trying backup...")
        if not check_node_connectivity(BACKUP_NODE_URL):
            log_error("Both nodes unreachable")
            return 1
    
    # Step 5: Download miner files
    log_info("Step 5: Downloading miner files...")
    if not download_miner_files():
        return 1
    
    # Step 6: Create virtual environment
    log_info("Step 6: Setting up Python environment...")
    if not create_virtual_environment():
        return 1
    
    # Step 7: Wallet setup
    log_info("Step 7: Wallet setup...")
    wallet_name = setup_wallet()
    
    # Step 8: Fingerprint check (optional)
    if args.run_fingerprint:
        log_info("Step 8: Running fingerprint checks...")
        run_fingerprint_check()
    
    # Step 9: Service installation (optional)
    if args.install_service:
        log_info("Step 9: Installing service...")
        install_service()
    
    print("\n" + "=" * 50)
    log_success("Setup complete!")
    log_info(f"Miner installed to: {INSTALL_DIR}")
    log_info(f"Wallet: {wallet_name}")
    print("=" * 50)
    log_info("To start mining, run: clawrtc start")
    
    return 0


def cmd_start(args):
    """Start mining"""
    config = load_config()
    wallet = config.get("wallet_name", "default")
    
    miner_file = MINER_DIR / "rustchain_linux_miner.py"
    
    if not miner_file.exists():
        log_error("Miner not set up. Run 'clawrtc setup' first.")
        return 1
    
    python = VENV_DIR / "bin" / "python"
    
    cmd = [str(python), str(miner_file), "--wallet", wallet, "--node", DEFAULT_NODE_URL]
    
    if args.threads:
        cmd.extend(["--threads", str(args.threads)])
    
    log_info(f"Starting miner with wallet: {wallet}")
    
    subprocess.run(cmd)
    return 0


def cmd_status(args):
    """Check mining status"""
    return 0 if check_health() else 1


def cmd_stop(args):
    """Stop mining"""
    os_name, _ = get_platform()
    
    if os_name == "linux":
        subprocess.run(["systemctl", "--user", "stop", SERVICE_NAME])
    elif os_name == "macos":
        subprocess.run(["launchctl", "unload", 
                       str(Path.home() / "Library/LaunchAgents/com.rustchain.miner.plist")])
    
    log_success("Miner stopped")
    return 0


def cmd_health(args):
    """Run health check"""
    return 0 if check_health() else 1


def main():
    parser = argparse.ArgumentParser(
        description="ClawRTC - RustChain Miner Setup Wizard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Run setup wizard")
    setup_parser.add_argument("--run-fingerprint", action="store_true",
                             help="Run fingerprint checks during setup")
    setup_parser.add_argument("--install-service", action="store_true",
                             help="Install systemd/launchd service")
    setup_parser.set_defaults(func=cmd_setup)
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start mining")
    start_parser.add_argument("--threads", type=int, help="Number of threads")
    start_parser.set_defaults(func=cmd_start)
    
    # Status command
    subparsers.add_parser("status", help="Check mining status").set_defaults(func=cmd_status)
    
    # Stop command
    subparsers.add_parser("stop", help="Stop mining").set_defaults(func=cmd_stop)
    
    # Health command
    subparsers.add_parser("health", help="Run health check").set_defaults(func=cmd_health)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
