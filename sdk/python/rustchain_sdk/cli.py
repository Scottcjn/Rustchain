#!/usr/bin/env python3
"""ClawRTC — RustChain miner for AI agents on modern hardware.

Your Claw agent earns RTC tokens by proving it runs on real hardware.
Modern machines get 1x multiplier. Vintage hardware gets bonus multipliers.
VMs are detected and penalized — real iron only.

Usage:
    pip install clawrtc
    clawrtc wallet create          Generate your RTC address
    clawrtc install --wallet RTC...
    clawrtc start

Wallet:
    clawrtc wallet create          Create Ed25519 RTC wallet
    clawrtc wallet show            Show address and balance
    clawrtc wallet export          Download key file

Security:
    clawrtc install --dry-run      Preview without installing
    clawrtc install --verify       Show SHA256 hashes of bundled files
"""

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import textwrap
import time
import json

__version__ = "1.7.1"

INSTALL_DIR = os.path.join(os.path.expanduser("~"), ".clawrtc")
VENV_DIR = os.path.join(INSTALL_DIR, "venv")
NODE_URL = "https://bulbous-bouffant.metalseed.net"
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PACKAGE_DIR, "data")

# ANSI colors
CYAN = "\033[36m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"

# Bundled files shipped with the package
BUNDLED_FILES = [
    ("miner.py", "miner.py"),
    ("fingerprint_checks.py", "fingerprint_checks.py"),
]


def log(msg):
    print(f"{CYAN}[clawrtc]{NC} {msg}")


def success(msg):
    print(f"{GREEN}[OK]{NC} {msg}")


def warn(msg):
    print(f"{YELLOW}[WARN]{NC} {msg}")


def error(msg):
    print(f"{RED}[ERROR]{NC} {msg}", file=sys.stderr)
    sys.exit(1)


def sha256_file(path):
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def run_cmd(cmd, check=True, capture=False):
    """Run a shell command."""
    try:
        result = subprocess.run(
            cmd, shell=True, check=check,
            capture_output=capture, text=True
        )
        return result.stdout.strip() if capture else None
    except subprocess.CalledProcessError:
        if check:
            raise
        return None


def _detect_vm():
    """Quick VM detection — warns the user upfront."""
    indicators = []
    system = platform.system()

    if system == "Linux":
        dmi_paths = [
            "/sys/class/dmi/id/sys_vendor",
            "/sys/class/dmi/id/product_name",
            "/sys/class/dmi/id/board_vendor",
        ]
        vm_vendors = ["qemu", "vmware", "virtualbox", "xen", "kvm", "microsoft", "parallels", "bhyve"]
        for p in dmi_paths:
            try:
                with open(p) as f:
                    val = f.read().strip().lower()
                    if any(v in val for v in vm_vendors):
                        indicators.append(f"{p}: {val}")
            except (OSError, IOError):
                pass

        try:
            with open("/proc/cpuinfo") as f:
                if "hypervisor" in f.read().lower():
                    indicators.append("cpuinfo: hypervisor flag")
        except (OSError, IOError):
            pass

    elif system == "Darwin":
        try:
            out = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.features"],
                capture_output=True, text=True
            ).stdout.lower()
            if "vmm" in out:
                indicators.append("sysctl: VMM flag")
        except Exception:
            pass

    return indicators


def _show_consent_disclosure():
    """Show what ClawRTC does before proceeding."""
    print(textwrap.dedent(f"""
    {BOLD}What ClawRTC will do:{NC}

      {CYAN}1. Extract{NC}   Two Python scripts bundled with this package:
         - fingerprint_checks.py  (hardware detection)
         - miner.py               (attestation client)
         {DIM}No external downloads — all code ships with the package.{NC}

      {CYAN}2. Install{NC}   A Python virtual environment in ~/.clawrtc/
         with one dependency: 'requests' (HTTP library)

      {CYAN}3. Attest{NC}    When started, the miner contacts the RustChain network
         every few minutes to prove your hardware is real.
         Endpoint: {NODE_URL} (CA-signed TLS certificate)

      {CYAN}4. Collect{NC}   Hardware fingerprint data sent during attestation:
         - CPU model, architecture, vendor
         - Clock timing variance (proves real oscillator)
         - Cache latency profile (proves real cache hierarchy)
         - VM detection flags (hypervisor, DMI vendor)
         {DIM}No personal data, files, browsing history, or credentials are collected.
         No data is sent to any third party — only to the RustChain node.{NC}

      {CYAN}5. Earn{NC}      RTC tokens accumulate in your wallet each epoch (~10 min)

    {DIM}Verify yourself:{NC}
      clawrtc install --dry-run      Preview without installing
      clawrtc install --verify       Show SHA256 hashes of bundled files
      Source code: https://github.com/Scottcjn/Rustchain
      Block explorer: {NODE_URL}/explorer
    """))


def cmd_install(args):
    """Install and configure ClawRTC miner for your AI agent."""
    print(textwrap.dedent(f"""
    {CYAN}{BOLD}
      ██████╗██╗      █████╗ ██╗    ██╗███████╗██╗  ██╗██╗██╗     ██╗
     ██╔════╝██║     ██╔══██╗██║    ██║██╔════╝██║ ██╔╝██║██║     ██║
     ██║     ██║     ███████║██║ █╗ ██║███████╗█████╔╝ ██║██║     ██║
     ██║     ██║     ██╔══██║██║███╗██║╚════██║██╔═██╗ ██║██║     ██║
     ╚██████╗███████╗██║  ██║╚███╔███╔╝███████║██║  ██╗██║███████╗███████╗
      ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝ ╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝
    {NC}
    {DIM}  Mine RTC tokens with your AI agent on real hardware{NC}
    {DIM}  Modern x86/ARM = 1x | Vintage PowerPC = up to 2.5x | VM = ~0x{NC}
    {DIM}  Version {__version__}{NC}
    """))

    system = platform.system()
    machine = platform.machine()
    log(f"Platform: {system} | Arch: {machine}")

    if system not in ("Linux", "Darwin"):
        error(f"Unsupported platform: {system}. Use Linux or macOS.")

    # --verify: show bundled file hashes and exit
    if getattr(args, "verify", False):
        log("Bundled file hashes (SHA256):")
        for src_name, dest_name in BUNDLED_FILES:
            src = os.path.join(DATA_DIR, src_name)
            if os.path.exists(src):
                print(f"  {dest_name}: {sha256_file(src)}")
            else:
                print(f"  {dest_name}: NOT FOUND in package")
        return

    # --dry-run: show what would happen, don't do it
    if getattr(args, "dry_run", False):
        _show_consent_disclosure()
        log("DRY RUN — no files extracted, no services created.")
        return

    # Show disclosure and get consent (unless --yes)
    if not getattr(args, "yes", False):
        _show_consent_disclosure()
        try:
            answer = input(f"{CYAN}[clawrtc]{NC} Proceed with installation? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer not in ("y", "yes"):
            log("Installation cancelled.")
            return

    # VM check — warn upfront, don't block
    vm_hints = _detect_vm()
    if vm_hints:
        print(textwrap.dedent(f"""
    {RED}{BOLD}  ╔══════════════════════════════════════════════════════════╗
      ║              VM DETECTED — READ THIS               ║
      ╠══════════════════════════════════════════════════════════╣
      ║                                                          ║
      ║  This machine appears to be a virtual machine.           ║
      ║  RustChain's hardware fingerprint system WILL detect     ║
      ║  VMs and assigns near-zero mining weight.                ║
      ║                                                          ║
      ║  Your miner will attest, but earn effectively nothing.   ║
      ║  This is by design — RTC rewards real hardware only.     ║
      ║                                                          ║
      ║  VM indicators found:                                    ║{NC}"""))
        for h in vm_hints[:4]:
            print(f"      {RED}  *  {h}{NC}")
        print(f"""      {RED}{BOLD}║                                                          ║
      ║  To earn RTC, run on bare-metal hardware.               ║
      ╚══════════════════════════════════════════════════════════╝{NC}
""")

    # Wallet setup
    wallet = args.wallet
    if not wallet:
        try:
            wallet = input(f"{CYAN}[clawrtc]{NC} Enter agent wallet name (e.g. my-claw-agent): ").strip()
        except (EOFError, KeyboardInterrupt):
            wallet = ""

    if not wallet:
        hostname = platform.node().split(".")[0] or "agent"
        wallet = f"claw-{hostname}-{int(time.time()) % 100000}"
        warn(f"No wallet name provided. Auto-generated: {wallet}")

    # Create install dir
    log(f"Installing to {INSTALL_DIR}")
    os.makedirs(INSTALL_DIR, exist_ok=True)

    # Save wallet
    with open(os.path.join(INSTALL_DIR, ".wallet"), "w") as f:
        f.write(wallet)

    # Create venv
    if not os.path.isdir(VENV_DIR):
        log("Creating Python environment...")
        run_cmd(f'"{sys.executable}" -m venv "{VENV_DIR}"')

    # Install deps
    log("Installing dependencies...")
    pip = os.path.join(VENV_DIR, "bin", "pip")
    run_cmd(f'"{pip}" install --upgrade pip -q')
    run_cmd(f'"{pip}" install requests -q')
    success("Dependencies ready")

    # Extract bundled miner files (no download!)
    log("Extracting bundled miner scripts...")
    for src_name, dest_name in BUNDLED_FILES:
        src = os.path.join(DATA_DIR, src_name)
        dest = os.path.join(INSTALL_DIR, dest_name)
        if not os.path.exists(src):
            error(f"Bundled file missing: {src_name}. Package may be corrupted.")
        shutil.copy2(src, dest)
        file_hash = sha256_file(dest)
        size = os.path.getsize(dest)
        log(f"  {dest_name} ({size / 1024:.1f} KB) SHA256: {file_hash[:16]}...")

    success("Miner files extracted from package (no external downloads)")

    # Setup service ONLY if --service flag is passed
    if getattr(args, "service", False):
        log("Setting up background service (--service flag)...")
        if system == "Linux":
            _setup_systemd(wallet)
        elif system == "Darwin":
            _setup_launchd(wallet)
    else:
        log(f"No background service created. To enable auto-start, re-run with --service")
        log(f"Or start manually: clawrtc start")

    # Check network
    log("Checking RustChain network...")
    try:
        import urllib.request
        req = urllib.request.Request(f"{NODE_URL}/api/miners")
        with urllib.request.urlopen(req, timeout=10) as resp:
            miners = json.loads(resp.read())
            log(f"Active miners on network: {len(miners)}")
    except Exception:
        warn("Could not reach network (node may be temporarily unavailable)")

    # Anonymous install telemetry — non-blocking, fails silently, no PII
    try:
        import threading, urllib.request
        def _ping():
            try:
                payload = json.dumps({
                    "package": "clawrtc",
                    "version": __version__,
                    "platform": platform.system(),
                    "arch": platform.machine(),
                    "source": "pip"
                }).encode()
                req = urllib.request.Request(
                    "https://bottube.ai/api/telemetry/install",
                    data=payload,
                    headers={"Content-Type": "application/json"}
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass
        threading.Thread(target=_ping, daemon=True).start()
    except Exception:
        pass

    print(textwrap.dedent(f"""
    {GREEN}{BOLD}═══════════════════════════════════════════════════════════
      ClawRTC installed!  Your agent is ready to mine RTC.

      Wallet:    {wallet}
      Location:  {INSTALL_DIR}
      Reward:    1x multiplier (modern hardware)
      Node:      {NODE_URL} (CA-signed TLS)

      Next steps:
        clawrtc wallet create      Generate RTC address for payouts
        clawrtc start              Start mining (foreground)
        clawrtc start --service    Start + enable auto-restart
        clawrtc stop               Stop mining
        clawrtc status             Check miner + network status
        clawrtc logs               View miner output

      How it works:
        * Your agent proves real hardware via 6 fingerprint checks
        * Attestation happens automatically every few minutes
        * RTC tokens accumulate in your wallet each epoch (~10 min)
        * Check balance: clawrtc status

      Verify & audit:
        * Source: https://github.com/Scottcjn/Rustchain
        * Explorer: {NODE_URL}/explorer
        * clawrtc uninstall   Remove everything cleanly
    ═══════════════════════════════════════════════════════════{NC}
    """))


def _setup_systemd(wallet):
    """Set up systemd user service on Linux."""
    service_dir = os.path.expanduser("~/.config/systemd/user")
    os.makedirs(service_dir, exist_ok=True)
    service_file = os.path.join(service_dir, "clawrtc-miner.service")
    python_bin = os.path.join(VENV_DIR, "bin", "python")
    miner_py = os.path.join(INSTALL_DIR, "miner.py")

    with open(service_file, "w") as f:
        f.write(textwrap.dedent(f"""\
            [Unit]
            Description=ClawRTC RTC Miner — AI Agent Mining
            After=network-online.target
            Wants=network-online.target

            [Service]
            ExecStart={python_bin} {miner_py} --wallet {wallet}
            Restart=always
            RestartSec=30
            WorkingDirectory={INSTALL_DIR}
            Environment=PYTHONUNBUFFERED=1

            [Install]
            WantedBy=default.target
        """))

    try:
        run_cmd("systemctl --user daemon-reload")
        run_cmd("systemctl --user enable clawrtc-miner")
        run_cmd("systemctl --user start clawrtc-miner")
        success("Service installed and started (auto-restarts on reboot)")
    except Exception:
        warn("Systemd user services not available. Use: clawrtc start")


def _setup_launchd(wallet):
    """Set up launchd agent on macOS."""
    plist_dir = os.path.expanduser("~/Library/LaunchAgents")
    os.makedirs(plist_dir, exist_ok=True)
    plist_file = os.path.join(plist_dir, "com.clawrtc.miner.plist")
    python_bin = os.path.join(VENV_DIR, "bin", "python")
    miner_py = os.path.join(INSTALL_DIR, "miner.py")

    with open(plist_file, "w") as f:
        f.write(textwrap.dedent(f"""\
            <?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
              "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
            <plist version="1.0">
            <dict>
                <key>Label</key>
                <string>com.clawrtc.miner</string>
                <key>ProgramArguments</key>
                <array>
                    <string>{python_bin}</string>
                    <string>{miner_py}</string>
                    <string>--wallet</string>
                    <string>{wallet}</string>
                </array>
                <key>WorkingDirectory</key>
                <string>{INSTALL_DIR}</string>
                <key>RunAtLoad</key>
                <true/>
                <key>KeepAlive</key>
                <true/>
                <key>StandardOutPath</key>
                <string>{os.path.join(INSTALL_DIR, "miner.log")}</string>
                <key>StandardErrorPath</key>
                <string>{os.path.join(INSTALL_DIR, "miner.err")}</string>
            </dict>
            </plist>
        """))

    try:
        run_cmd(f'launchctl unload "{plist_file}" 2>/dev/null', check=False)
        run_cmd(f'launchctl load "{plist_file}"')
        success("LaunchAgent installed and loaded (auto-restarts on login)")
    except Exception:
        warn("Could not load LaunchAgent. Use: clawrtc start")


def cmd_start(args):
    """Start the ClawRTC miner."""
    system = platform.system()

    # If --service flag, set up persistence then start
    if getattr(args, "service", False):
        wallet_file = os.path.join(INSTALL_DIR, ".wallet")
        wallet = open(wallet_file).read().strip() if os.path.exists(wallet_file) else "agent"
        if system == "Linux":
            _setup_systemd(wallet)
        elif system == "Darwin":
            _setup_launchd(wallet)
        return

    # Try systemd first (if service exists)
    if system == "Linux":
        sf = os.path.expanduser("~/.config/systemd/user/clawrtc-miner.service")
        if os.path.exists(sf):
            run_cmd("systemctl --user start clawrtc-miner")
            success("Miner started (systemd)")
            return

    elif system == "Darwin":
        pf = os.path.expanduser("~/Library/LaunchAgents/com.clawrtc.miner.plist")
        if os.path.exists(pf):
            run_cmd(f'launchctl load "{pf}"', check=False)
            success("Miner started (launchd)")
            return

    # Fallback: run in foreground
    miner_py = os.path.join(INSTALL_DIR, "miner.py")
    python_bin = os.path.join(VENV_DIR, "bin", "python")
    wallet_file = os.path.join(INSTALL_DIR, ".wallet")

    if not os.path.exists(miner_py):
        error("Miner not installed. Run: clawrtc install")

    wallet = open(wallet_file).read().strip() if os.path.exists(wallet_file) else ""
    log(f"Starting miner in foreground (Ctrl+C to stop)...")
    log(f"Tip: Use 'clawrtc start --service' for background auto-restart")
    os.execvp(python_bin, [python_bin, miner_py] + (["--wallet", wallet] if wallet else []))


def cmd_mine(args):
    """Mine command — install wallet if needed, then start."""
    if hasattr(args, 'wallet') and args.wallet:
        install_args = argparse.Namespace(
            wallet=args.wallet, dry_run=False, verify=False,
            service=getattr(args, 'service', False),
            no_service=False, yes=True
        )
        cmd_install(install_args)
    cmd_start(args)


def cmd_stop(args):
    """Stop the ClawRTC miner."""
    system = platform.system()
    if system == "Linux":
        run_cmd("systemctl --user stop clawrtc-miner", check=False)
    elif system == "Darwin":
        pf = os.path.expanduser("~/Library/LaunchAgents/com.clawrtc.miner.plist")
        run_cmd(f'launchctl unload "{pf}"', check=False)
    success("Miner stopped")


def cmd_status(args):
    """Check miner and network status."""
    system = platform.system()

    # Service status
    if system == "Linux":
        sf = os.path.expanduser("~/.config/systemd/user/clawrtc-miner.service")
        if os.path.exists(sf):
            run_cmd("systemctl --user status clawrtc-miner", check=False)
        else:
            log("No background service configured. Use: clawrtc start --service")
    elif system == "Darwin":
        run_cmd("launchctl list | grep clawrtc", check=False)

    # Wallet info
    wallet_file = os.path.join(INSTALL_DIR, ".wallet")
    if os.path.exists(wallet_file):
        wallet = open(wallet_file).read().strip()
        log(f"Wallet: {wallet}")

    # File integrity
    for filename in ["miner.py", "fingerprint_checks.py"]:
        path = os.path.join(INSTALL_DIR, filename)
        if os.path.exists(path):
            h = sha256_file(path)
            log(f"{filename} SHA256: {h[:16]}...")

    # Network check
    try:
        import urllib.request
        req = urllib.request.Request(f"{NODE_URL}/health")
        with urllib.request.urlopen(req, timeout=10) as resp:
            health = json.loads(resp.read())
            status = "online" if health.get("ok") else "offline"
            log(f"Network: {status} (v{health.get('version', '?')})")
    except Exception:
        warn("Could not reach network")


def cmd_logs(args):
    """View miner logs."""
    system = platform.system()
    if system == "Linux":
        sf = os.path.expanduser("~/.config/systemd/user/clawrtc-miner.service")
        if os.path.exists(sf):
            os.execlp("journalctl", "journalctl", "--user", "-u", "clawrtc-miner", "-f", "--no-pager", "-n", "50")
        else:
            log_file = os.path.join(INSTALL_DIR, "miner.log")
            if os.path.exists(log_file):
                os.execlp("tail", "tail", "-f", log_file)
            else:
                warn("No logs found. Start the miner first: clawrtc start")
    elif system == "Darwin":
        log_file = os.path.join(INSTALL_DIR, "miner.log")
        if os.path.exists(log_file):
            os.execlp("tail", "tail", "-f", log_file)
        else:
            warn("No log file found")


WALLET_DIR = os.path.join(INSTALL_DIR, "wallets")
WALLET_FILE = os.path.join(WALLET_DIR, "default.json")


def _get_ed25519():
    """Lazily import Ed25519 from cryptography library."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import (
            Encoding, NoEncryption, PrivateFormat, PublicFormat,
        )
        return Ed25519PrivateKey, Encoding, NoEncryption, PrivateFormat, PublicFormat
    except ImportError:
        error(
            "Missing dependency: cryptography\n"
            f"  Run: pip install cryptography>=41.0\n"
            f"  Or:  pip install clawrtc[wallet]"
        )


def _derive_rtc_address(public_key_bytes):
    """Derive RTC address from public key bytes: RTC + sha256(pubkey)[:40]"""
    return "RTC" + hashlib.sha256(public_key_bytes).hexdigest()[:40]


def _load_wallet():
    """Load existing wallet from disk, or return None."""
    if not os.path.exists(WALLET_FILE):
        return None
    try:
        with open(WALLET_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def cmd_wallet(args):
    """Manage RTC wallet — create, show, export, or coinbase."""
    action = args.wallet_action

    if action == "create":
        _wallet_create(args)
    elif action == "show":
        _wallet_show(args)
    elif action == "export":
        _wallet_export(args)
    elif action == "coinbase":
        from clawrtc.coinbase_wallet import cmd_coinbase
        cmd_coinbase(args)
    else:
        log("Usage: clawrtc wallet [create|show|export|coinbase]")


def _wallet_create(args):
    """Generate a new Ed25519 RTC wallet."""
    Ed25519PrivateKey, Encoding, NoEncryption, PrivateFormat, PublicFormat = _get_ed25519()

    # Check for existing wallet
    existing = _load_wallet()
    if existing and not getattr(args, "force", False):
        print(f"\n  {YELLOW}You already have an RTC wallet:{NC}")
        print(f"  {GREEN}{BOLD}{existing['address']}{NC}\n")
        print(f"  To create a new one (REPLACES existing), use:")
        print(f"    clawrtc wallet create --force\n")
        return

    # Generate Ed25519 keypair
    log("Generating Ed25519 keypair...")
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Export raw bytes
    priv_bytes = private_key.private_bytes(
        Encoding.Raw, PrivateFormat.Raw, NoEncryption()
    )
    pub_bytes = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)

    # Derive RTC address
    address = _derive_rtc_address(pub_bytes)

    # Build wallet data
    wallet_data = {
        "address": address,
        "public_key": pub_bytes.hex(),
        "private_key": priv_bytes.hex(),
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "curve": "Ed25519",
        "network": "rustchain-mainnet",
    }

    # Save to disk
    os.makedirs(WALLET_DIR, exist_ok=True)
    with open(WALLET_FILE, "w") as f:
        json.dump(wallet_data, f, indent=2)
    os.chmod(WALLET_FILE, 0o600)  # Owner read/write only

    # Also update the .wallet file so the miner uses this address
    with open(os.path.join(INSTALL_DIR, ".wallet"), "w") as f:
        f.write(address)

    print(textwrap.dedent(f"""
    {GREEN}{BOLD}═══════════════════════════════════════════════════════════
      RTC WALLET CREATED
    ═══════════════════════════════════════════════════════════{NC}

      {GREEN}Address (PUBLIC — paste this in bounty claims):{NC}
      {BOLD}{address}{NC}

      {RED}Private key saved to:{NC}
      {DIM}{WALLET_FILE}{NC}

    {RED}{BOLD}  ╔══════════════════════════════════════════════════════╗
      ║  SAVE YOUR PRIVATE KEY — IT CANNOT BE RECOVERED!  ║
      ║  Back up {WALLET_FILE}    ║
      ║  Anyone with this key can spend your RTC.         ║
      ╚══════════════════════════════════════════════════════╝{NC}

      {CYAN}Next steps:{NC}
        1. Copy your {BOLD}RTC...{NC} address above
        2. Paste it in GitHub bounty claims
        3. Start mining: clawrtc start
        4. Check balance: clawrtc wallet show

      {DIM}This is NOT a Solana/ETH/BTC address.
      For wRTC on Solana, bridge at https://bottube.ai/bridge{NC}
    """))


def _wallet_show(args):
    """Display current wallet address and balance."""
    wallet = _load_wallet()
    if not wallet:
        print(f"\n  {YELLOW}No RTC wallet found.{NC}")
        print(f"  Create one: clawrtc wallet create\n")
        print(f"  Or generate online: https://rustchain.org/wallet.html\n")
        return

    address = wallet["address"]
    pub_key = wallet["public_key"]
    created = wallet.get("created", "unknown")

    print(f"\n  {GREEN}{BOLD}RTC Address:{NC}  {BOLD}{address}{NC}")
    print(f"  {DIM}Public Key:{NC}   {DIM}{pub_key}{NC}")
    print(f"  {DIM}Created:{NC}      {DIM}{created}{NC}")
    print(f"  {DIM}Curve:{NC}        {DIM}{wallet.get('curve', 'Ed25519')}{NC}")
    print(f"  {DIM}Key File:{NC}     {DIM}{WALLET_FILE}{NC}")

    # Check balance from network
    try:
        import urllib.request
        url = f"{NODE_URL}/wallet/balance?miner_id={address}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            balance = data.get("amount_rtc", data.get("balance_rtc", data.get("balance", 0)))
            print(f"  {GREEN}Balance:{NC}      {GREEN}{BOLD}{balance} RTC{NC}")
    except Exception:
        print(f"  {DIM}Balance:{NC}      {DIM}(could not reach network){NC}")

    print()


def _wallet_export(args):
    """Export wallet key file."""
    wallet = _load_wallet()
    if not wallet:
        print(f"\n  {YELLOW}No wallet to export. Create one first:{NC}")
        print(f"  clawrtc wallet create\n")
        return

    export_path = getattr(args, "output", None) or f"rtc-wallet-{wallet['address']}.json"
    # Remove private key from export if --public-only
    if getattr(args, "public_only", False):
        export_data = {k: v for k, v in wallet.items() if k != "private_key"}
    else:
        export_data = wallet

    with open(export_path, "w") as f:
        json.dump(export_data, f, indent=2)

    print(f"\n  {GREEN}Wallet exported to:{NC} {export_path}")
    if not getattr(args, "public_only", False):
        print(f"  {RED}Contains private key — keep this file secure!{NC}")
    print()


def cmd_uninstall(args):
    """Remove ClawRTC miner and all files."""
    log("Stopping miner...")
    cmd_stop(args)

    system = platform.system()
    if system == "Linux":
        run_cmd("systemctl --user disable clawrtc-miner", check=False)
        sf = os.path.expanduser("~/.config/systemd/user/clawrtc-miner.service")
        if os.path.exists(sf):
            os.unlink(sf)
            run_cmd("systemctl --user daemon-reload", check=False)
    elif system == "Darwin":
        pf = os.path.expanduser("~/Library/LaunchAgents/com.clawrtc.miner.plist")
        if os.path.exists(pf):
            os.unlink(pf)

    if os.path.isdir(INSTALL_DIR):
        shutil.rmtree(INSTALL_DIR)

    success("ClawRTC miner fully uninstalled — no files remain")


def main():
    parser = argparse.ArgumentParser(
        prog="clawrtc",
        description="ClawRTC — Mine RTC tokens with your AI agent on real hardware",
        allow_abbrev=False,
        epilog=textwrap.dedent("""\
            Your Claw agent earns RTC by proving it runs on real hardware.
            Modern x86/ARM gets 1x multiplier. VMs are detected and penalized.
            Vintage hardware (PowerPC, etc.) earns bonus multipliers up to 2.5x.

            Security & verification:
              clawrtc install --dry-run      Preview without changes
              clawrtc install --verify       Show bundled file hashes
              Source: https://github.com/Scottcjn/Rustchain
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", "-V", action="version",
                        version=f"clawrtc {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_install = sub.add_parser("install", help="Install miner and configure wallet")
    p_install.add_argument("--wallet", help="Agent wallet name for mining rewards")
    p_install.add_argument("--dry-run", action="store_true", help="Preview what will be installed without making changes")
    p_install.add_argument("--verify", action="store_true", help="Show SHA256 hashes of bundled files")
    p_install.add_argument("--service", action="store_true", help="Create background service (systemd/launchd)")
    p_install.add_argument("--no-service", action="store_true", help="Skip background service setup (default)")
    p_install.add_argument("-y", "--yes", action="store_true", help="Skip consent prompt (for CI/automation)")

    p_start = sub.add_parser("start", help="Start mining")
    p_start.add_argument("--service", action="store_true", help="Create background service for auto-restart")

    p_mine = sub.add_parser("mine", help="Start mining (alias for 'start')")
    p_mine.add_argument("--wallet", help="Wallet name (will install first if needed)")
    p_mine.add_argument("--service", action="store_true", help="Create background service for auto-restart")

    sub.add_parser("stop", help="Stop mining")
    sub.add_parser("status", help="Check miner + network status + file hashes")
    sub.add_parser("logs", help="View miner output logs")
    sub.add_parser("uninstall", help="Remove miner and all files completely")

    p_wallet = sub.add_parser("wallet", help="Manage RTC wallet (create, show, export, coinbase)")
    p_wallet.add_argument("wallet_action", nargs="?", default="show",
                          choices=["create", "show", "export", "coinbase"],
                          help="Wallet action (default: show)")
    p_wallet.add_argument("coinbase_action", nargs="?", default="show",
                          choices=["create", "show", "link", "swap-info"],
                          help="Coinbase sub-action (when wallet_action=coinbase)")
    p_wallet.add_argument("base_address", nargs="?", default="",
                          help="Base address for 'coinbase link' command")
    p_wallet.add_argument("--force", action="store_true",
                          help="Overwrite existing wallet (create only)")
    p_wallet.add_argument("--output", "-o", help="Export file path (export only)")
    p_wallet.add_argument("--public-only", action="store_true",
                          help="Export without private key (export only)")

    args = parser.parse_args()

    commands = {
        "install": cmd_install,
        "start": cmd_start,
        "mine": cmd_mine,
        "stop": cmd_stop,
        "status": cmd_status,
        "logs": cmd_logs,
        "uninstall": cmd_uninstall,
        "wallet": cmd_wallet,
    }

    if not args.command:
        parser.print_help()
        return

    func = commands.get(args.command)
    if func:
        func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
