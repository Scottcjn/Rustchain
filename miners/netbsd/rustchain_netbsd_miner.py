#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""RustChain miner client for NetBSD (bounty #12788).

This is a NetBSD-native port of the RustChain Linux miner client. It reuses
the Linux miner's enrollment, attestation, signing, and mining core, and
replaces only the hardware probes with NetBSD-native sysctl lookups so that
every attested value is measured on this machine, never guessed:

    sysctl -n machdep.cpu_model    -> CPU model string
    sysctl -n hw.machine           -> architecture (amd64, evbarm, sparc64, ...)
    sysctl -n hw.ncpuonline        -> online core count
    sysctl -n hw.physmem64         -> physical memory in bytes
    sysctl -n kern.ostype          -> must report "NetBSD"
    ifconfig <iface>               -> real interface MAC addresses ("address: ...")

The client refuses to run on non-NetBSD systems: quietly attesting hardware
measured on a different OS would fabricate the device fingerprint.

Verify-before-trust:

    ./rustchain_netbsd_miner.py --dry-run        # preflight, read-only health probe
    ./rustchain_netbsd_miner.py --show-payload   # with --dry-run: print node response
    ./rustchain_netbsd_miner.py --test-only      # local hardware detection, no network
    ./rustchain_netbsd_miner.py --wallet NAME    # real mining
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import platform
import re
import socket
import subprocess
import sys
import types
from pathlib import Path

# NetBSD sysctl keys used for honest hardware detection. hw.physmem64 is
# preferred over the legacy hw.physmem because it is 64-bit on all ports.
CPU_SYSCTL_KEYS = ("machdep.cpu_model", "machdep.cpu_brand_string")
CORES_SYSCTL_KEYS = ("hw.ncpuonline", "hw.ncpu")
MEMORY_SYSCTL_KEYS = ("hw.physmem64", "hw.physmem")

# Interfaces that do not belong to real hardware are filtered from the MAC
# signal, mirroring the Linux miner's virtual-interface policy.
VIRTUAL_IFACE_PREFIXES = (
    "lo", "tap", "tun", "bridge", "gif", "gre", "wg", "sl", "ppp", "stf", "vlan",
)


def assert_netbsd_platform():
    """Refuse to run anywhere except NetBSD.

    The bounty requires honest attestation: hardware values measured by this
    port are only trustworthy on NetBSD. Running on another OS and still
    calling this the "NetBSD miner" would fabricate the platform.
    """
    system = platform.system()
    if system != "NetBSD":
        raise SystemExit(
            "[ERROR] The RustChain NetBSD miner must run on NetBSD "
            f"(detected: {system or 'unknown'}). "
            "Refusing to attest hardware from another platform - "
            "that would fabricate the device fingerprint."
        )


def _netbsd_sysctl(key, timeout=5):
    """Return the raw value of a NetBSD sysctl key, or an empty string."""
    try:
        result = subprocess.run(
            ["sysctl", "-n", key],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
        )
        return (result.stdout or "").strip()
    except Exception:
        return ""


def _parse_int(value):
    """Parse a positive integer, returning None for anything else."""
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _classify_family(machine):
    """Map a NetBSD hw.machine value to a device family.

    This mirrors the Linux miner's honest platform.machine() classification
    so the node sees the same family naming across ports.
    """
    machine = (machine or "").lower()
    if machine in ("aarch64", "arm64", "aarch64eb"):
        return "ARM", "aarch64"
    if machine == "evbarm":
        return "ARM", "unknown"
    if machine in ("arm", "armv7", "armv6", "earmv7", "earmv6"):
        return "ARM", "armv7"
    if machine in ("ppc", "ppc64", "powerpc", "powerpc64", "macppc", "prep", "ofppc"):
        return "PowerPC", "powerpc"
    if machine in ("sparc", "sparc64", "sun4u", "sun4v"):
        return "SPARC", "sparc"
    if machine in ("mips", "mips64", "mipsel", "mips64el", "evbmips", "sgimips"):
        return "MIPS", "mips"
    if machine in ("riscv64", "riscv32", "riscv"):
        return "RISC-V", "riscv"
    if machine in ("m68k", "amiga", "atari", "mac68k", "mvme68k"):
        return "M68K", "68000"
    if machine in ("ia64",):
        return "IA-64", "itanium"
    if machine in ("s390", "s390x"):
        return "S390", "s390"
    if machine.startswith("sh"):
        return "SuperH", machine
    if machine in ("amd64", "x86_64"):
        return "x86", "amd64"
    if machine in ("i386", "i486", "i586", "i686", "x86"):
        return "x86", machine
    return "unknown", "unknown"


def _load_core_miner():
    """Lazily load the RustChain Linux miner core module.

    Two layouts are supported:
      * installer layout: this file sits next to rustchain_miner.py (in
        /opt/rustchain) alongside fingerprint_checks.py and miner_crypto.py
      * repository layout: this file is at miners/netbsd/ and the core is at
        miners/linux/rustchain_linux_miner.py
    """
    here = Path(__file__).resolve().parent
    candidates = [
        here / "rustchain_miner.py",
        here.parent / "linux" / "rustchain_linux_miner.py",
    ]
    for candidate in candidates:
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location(
                "rustchain_linux_miner_core", candidate
            )
            if spec is None or spec.loader is None:  # pragma: no cover - defensive
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules["rustchain_linux_miner_core"] = module
            try:
                spec.loader.exec_module(module)
            except ImportError as exc:
                raise SystemExit(
                    f"[ERROR] Could not load the miner core ({candidate.name}): {exc}. "
                    "Install the miner requirements first (see miners/netbsd/README.md)."
                ) from exc
            return module
    raise SystemExit(
        "[ERROR] The RustChain Linux miner core (rustchain_miner.py) was not "
        "found next to this file or at ../linux/rustchain_linux_miner.py. "
        "Use install-miner-netbsd.sh, which downloads and checksum-verifies it."
    )


def _netbsd_get_mac_addresses(self):
    """Return real MAC addresses read from NetBSD `ifconfig`.

    NetBSD prints each interface's link address as an "address: XX:XX:..."
    line, which the Linux miner's `ip`/`ether` parsers do not understand.
    Virtual and loopback interfaces are excluded, matching the core miner's
    policy. Falls back to the core miner's probe (and its honest sentinel)
    if nothing is found here.
    """
    macs = []
    try:
        iface_list = subprocess.run(
            ["ifconfig", "-l"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        ).stdout.split()
    except Exception:
        iface_list = []
    for iface in iface_list:
        if iface.startswith(VIRTUAL_IFACE_PREFIXES):
            continue
        try:
            output = subprocess.run(
                ["ifconfig", iface],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            ).stdout
        except Exception:
            continue
        match = re.search(r"address:\s*([0-9a-fA-F:]{17})", output)
        if match:
            mac = match.group(1).lower()
            if mac != "00:00:00:00:00:00" and mac not in macs:
                macs.append(mac)
    if macs:
        return macs[:3]
    # Do not let the Linux probe or its placeholder MAC stand in for a
    # NetBSD measurement when no physical interface address was readable.
    return []


def _netbsd_get_hw_info(self):
    """Collect hardware info with NetBSD-native sysctl probes.

    Replaces the core miner's Linux-oriented probes (lscpu, nproc, free).
    Values that cannot be measured are reported as unknown/None rather than
    defaulted, because invented values are fingerprint fabrication.
    """
    system = _netbsd_sysctl("kern.ostype")
    machine = _netbsd_sysctl("hw.machine_arch") or _netbsd_sysctl("hw.machine")
    family, arch = _classify_family(machine)

    cpu = ""
    for key in CPU_SYSCTL_KEYS:
        cpu = _netbsd_sysctl(key)
        if cpu:
            break
    cores = None
    for key in CORES_SYSCTL_KEYS:
        cores = _parse_int(_netbsd_sysctl(key))
        if cores:
            break

    memory_bytes = None
    for key in MEMORY_SYSCTL_KEYS:
        memory_bytes = _parse_int(_netbsd_sysctl(key))
        if memory_bytes:
            break
    macs = self._get_mac_addresses()

    hw = {
        "platform": system,
        "machine": machine,
        "hostname": socket.gethostname(),
        "family": family,
        "arch": arch,
        # The NetBSD port measures hardware natively; the core miner's
        # "not a primary supported platform" warning does not apply.
        "probe_warning": "",
        "cpu": cpu or "Unknown",
        "cores": cores,
        "memory_gb": round(memory_bytes / (1024 ** 3), 1) if memory_bytes else None,
        "macs": macs,
        "mac": macs[0] if macs else None,
    }
    self.hw_info = hw
    return hw


def _test_only(miner):
    """Run hardware detection locally. No network, no attestation."""
    print("\n[TEST-ONLY] NetBSD hardware detection (local only, no attestation)")
    hw = miner._get_hw_info()
    print(f"[TEST-ONLY]   kern.ostype:    {_netbsd_sysctl('kern.ostype') or 'unknown'}")
    print(f"[TEST-ONLY]   kern.osrelease: {_netbsd_sysctl('kern.osrelease') or 'unknown'}")
    print(f"[TEST-ONLY]   CPU:            {hw['cpu']}")
    print(f"[TEST-ONLY]   Machine:        {hw['machine']}")
    print(f"[TEST-ONLY]   Family/Arch:    {hw['family']}/{hw['arch']}")
    print(f"[TEST-ONLY]   Cores:          {hw['cores']}")
    print(
        "[TEST-ONLY]   Memory(GB):     "
        f"{hw['memory_gb'] if hw['memory_gb'] is not None else 'unknown'}"
    )
    print(f"[TEST-ONLY]   MAC count:      {len(hw['macs'])}")
    print(
        "[TEST-ONLY]   MACs:           "
        f"{', '.join(hw['macs']) if hw['macs'] else 'none detected'}"
    )
    print("[TEST-ONLY] No attestation was sent. Run without --test-only to mine.")
    return 0


def main(argv=None):
    # Honest-attestation guard: refuse before touching the network or keys.
    assert_netbsd_platform()

    core = _load_core_miner()

    # Optional node override for test setups; defaults to https://rustchain.org.
    node_url = os.environ.get("RUSTCHAIN_NODE")
    if node_url:
        core.NODE_URL = node_url

    parser = argparse.ArgumentParser(
        description="RustChain NetBSD Miner (RIP-PoA hardware attestation)",
    )
    parser.add_argument(
        "--version", "-v", action="version",
        version="RustChain NetBSD Miner v2.2.1-rip200-netbsd",
    )
    parser.add_argument("--wallet", help="Wallet address")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run preflight checks only; print hardware fingerprint info; do not start mining",
    )
    parser.add_argument(
        "--test-only",
        action="store_true",
        help="Run local NetBSD hardware detection without attesting or using the network",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output showing API endpoints, headers, and response details",
    )
    parser.add_argument(
        "--show-payload",
        action="store_true",
        help="Show request payloads and node responses during dry-run",
    )
    args = parser.parse_args(argv)

    miner = core.LocalMiner(
        wallet=args.wallet,
        verbose=args.verbose,
        show_payload=args.show_payload,
        persist_key=not (args.dry_run or args.test_only),
    )
    # Replace the core miner's Linux hardware probes with the NetBSD ones.
    miner._get_hw_info = types.MethodType(_netbsd_get_hw_info, miner)
    miner._get_mac_addresses = types.MethodType(_netbsd_get_mac_addresses, miner)
    miner._core_class = core.LocalMiner
    print("[NETBSD] NetBSD-native sysctl hardware probes active (machdep.*, hw.*)")

    if args.test_only:
        return _test_only(miner)
    if args.dry_run:
        result = miner.dry_run()
    else:
        result = miner.mine()
    return 0 if result in (None, True) else int(result)


if __name__ == "__main__":
    sys.exit(main())

