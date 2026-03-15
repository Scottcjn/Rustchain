#!/usr/bin/env python3
"""
RustChain Node Configuration Validator

Validates environment variables, ports, database connectivity, wallet files,
SSL certificates, network reachability, and recommends optimal settings
based on detected hardware.

Usage:
    python validate.py              # interactive summary
    python validate.py --json       # machine-readable output
    python validate.py --fix        # attempt to auto-fix simple issues
"""

import argparse
import json
import os
import platform
import shutil
import socket
import sqlite3
import ssl
import struct
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_ENV_VARS = {
    "RUSTCHAIN_HOME": "Base directory for RustChain data (default: /rustchain)",
    "RUSTCHAIN_DB": "Path to the SQLite database file",
}

OPTIONAL_ENV_VARS = {
    "DOWNLOAD_DIR": "Directory for downloads",
    "RUSTCHAIN_DASHBOARD_PORT": "Dashboard HTTP port (default: 8099)",
    "NODE_API_PORT": "API endpoint port (default: 8088)",
    "NGINX_HTTP_PORT": "Nginx HTTP port (default: 80)",
    "NGINX_HTTPS_PORT": "Nginx HTTPS port (default: 443)",
    "ENABLE_SSL": "Enable HTTPS (true/false)",
    "SSL_CERT_PATH": "Path to SSL certificate",
    "SSL_KEY_PATH": "Path to SSL private key",
    "LOG_LEVEL": "Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    "WALLET_NAME": "Wallet identifier for mining",
    "NODE_URL": "Public URL of the RustChain node",
    "BLOCK_TIME": "Block time in seconds (default: 600)",
    "RUSTCHAIN_NODE_MEMORY": "Docker memory limit",
    "RUSTCHAIN_NODE_CPUS": "Docker CPU limit",
    "RUN_AS_NON_ROOT": "Run container as non-root (true/false)",
    "TIP_BOT_WALLET": "Payout wallet address for bounty distributions",
    "BRIDGE_DB_PATH": "Path to bridge ledger database",
    "RUSTCHAIN_ADMIN_KEY": "Admin key for protected endpoints",
    "EXPORTER_PORT": "Prometheus exporter port (default: 9100)",
}

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

DEFAULT_PORTS = {
    "RUSTCHAIN_DASHBOARD_PORT": 8099,
    "NODE_API_PORT": 8088,
    "NGINX_HTTP_PORT": 80,
    "NGINX_HTTPS_PORT": 443,
    "EXPORTER_PORT": 9100,
}

KNOWN_ENDPOINTS = [
    ("rustchain.org", 443),
    ("50.28.86.131", 443),
]

WALLET_DIR_CANDIDATES = [
    Path.home() / ".rustchain",
    Path.home() / ".rustchain" / "wallets",
    Path("/rustchain") / "wallets",
]


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

@dataclass
class Check:
    name: str
    status: str  # "pass", "warn", "fail", "skip"
    message: str
    detail: str = ""

    def as_dict(self) -> Dict[str, str]:
        d = {"name": self.name, "status": self.status, "message": self.message}
        if self.detail:
            d["detail"] = self.detail
        return d


@dataclass
class ValidationReport:
    checks: List[Check] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def add(self, check: Check):
        self.checks.append(check)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.status == "pass")

    @property
    def warnings(self) -> int:
        return sum(1 for c in self.checks if c.status == "warn")

    @property
    def failures(self) -> int:
        return sum(1 for c in self.checks if c.status == "fail")

    @property
    def skipped(self) -> int:
        return sum(1 for c in self.checks if c.status == "skip")

    @property
    def overall(self) -> str:
        if self.failures > 0:
            return "FAIL"
        if self.warnings > 0:
            return "WARN"
        return "PASS"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "overall": self.overall,
            "summary": {
                "passed": self.passed,
                "warnings": self.warnings,
                "failures": self.failures,
                "skipped": self.skipped,
            },
            "checks": [c.as_dict() for c in self.checks],
            "recommendations": self.recommendations,
        }


# ---------------------------------------------------------------------------
# Individual validators
# ---------------------------------------------------------------------------

def check_required_env(report: ValidationReport) -> None:
    """Verify that all required environment variables are set."""
    for var, description in REQUIRED_ENV_VARS.items():
        val = os.environ.get(var)
        if val:
            report.add(Check(
                f"env.{var}",
                "pass",
                f"{var} is set",
                detail=f"value={val}",
            ))
        else:
            report.add(Check(
                f"env.{var}",
                "fail",
                f"{var} is not set — {description}",
            ))

    for var, description in OPTIONAL_ENV_VARS.items():
        val = os.environ.get(var)
        if val:
            report.add(Check(
                f"env.{var}",
                "pass",
                f"{var} is set",
                detail=f"value={val}",
            ))
        else:
            report.add(Check(
                f"env.{var}",
                "skip",
                f"Optional {var} not set — {description}",
            ))

    # Validate LOG_LEVEL value when present
    log_level = os.environ.get("LOG_LEVEL", "").upper()
    if log_level and log_level not in VALID_LOG_LEVELS:
        report.add(Check(
            "env.LOG_LEVEL.value",
            "warn",
            f"LOG_LEVEL='{log_level}' is not a recognised level",
            detail=f"Expected one of: {', '.join(sorted(VALID_LOG_LEVELS))}",
        ))


def check_port_ranges(report: ValidationReport) -> None:
    """Validate configured ports are within acceptable ranges."""
    for env_var, default in DEFAULT_PORTS.items():
        raw = os.environ.get(env_var)
        port = default if raw is None else raw

        try:
            port_int = int(port)
        except (ValueError, TypeError):
            report.add(Check(
                f"port.{env_var}",
                "fail",
                f"{env_var} value '{port}' is not a valid integer",
            ))
            continue

        if not (1 <= port_int <= 65535):
            report.add(Check(
                f"port.{env_var}",
                "fail",
                f"{env_var}={port_int} is outside valid range 1-65535",
            ))
        elif port_int < 1024 and os.getuid() != 0 if hasattr(os, "getuid") else False:
            report.add(Check(
                f"port.{env_var}",
                "warn",
                f"{env_var}={port_int} is a privileged port — may require root",
            ))
        else:
            report.add(Check(
                f"port.{env_var}",
                "pass",
                f"{env_var}={port_int} is valid",
            ))

        # Check if port is already bound
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(("127.0.0.1", port_int))
                if result == 0:
                    report.add(Check(
                        f"port.{env_var}.conflict",
                        "warn",
                        f"Port {port_int} ({env_var}) is already in use",
                    ))
        except OSError:
            pass


def check_database(report: ValidationReport) -> None:
    """Verify that the configured SQLite database is accessible."""
    db_path = os.environ.get("RUSTCHAIN_DB", "")
    if not db_path:
        report.add(Check(
            "db.connectivity",
            "skip",
            "RUSTCHAIN_DB not set — skipping database check",
        ))
        return

    db_file = Path(db_path)

    if not db_file.exists():
        # Might be first run; check parent directory is writable
        parent = db_file.parent
        if parent.exists() and os.access(str(parent), os.W_OK):
            report.add(Check(
                "db.connectivity",
                "warn",
                f"Database file does not exist yet ({db_path}), "
                "but parent directory is writable — will be created on first run",
            ))
        else:
            report.add(Check(
                "db.connectivity",
                "fail",
                f"Database file does not exist ({db_path}) and parent "
                "directory is missing or not writable",
            ))
        return

    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.execute("SELECT 1")

        # Quick integrity check
        result = conn.execute("PRAGMA integrity_check").fetchone()
        if result and result[0] == "ok":
            report.add(Check(
                "db.connectivity",
                "pass",
                "Database is accessible and passes integrity check",
                detail=f"path={db_path}",
            ))
        else:
            report.add(Check(
                "db.connectivity",
                "warn",
                "Database is accessible but integrity check returned warnings",
                detail=str(result),
            ))

        # Check for expected tables
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if tables:
            report.add(Check(
                "db.tables",
                "pass",
                f"Database contains {len(tables)} table(s)",
                detail=", ".join(sorted(tables)),
            ))
        else:
            report.add(Check(
                "db.tables",
                "warn",
                "Database exists but contains no tables — may need initialisation",
            ))
        conn.close()
    except sqlite3.Error as exc:
        report.add(Check(
            "db.connectivity",
            "fail",
            f"Cannot connect to database: {exc}",
            detail=f"path={db_path}",
        ))

    # Check bridge DB if configured
    bridge_db = os.environ.get("BRIDGE_DB_PATH")
    if bridge_db:
        if Path(bridge_db).exists():
            try:
                conn = sqlite3.connect(bridge_db, timeout=5)
                conn.execute("SELECT 1")
                conn.close()
                report.add(Check(
                    "db.bridge",
                    "pass",
                    "Bridge database is accessible",
                    detail=f"path={bridge_db}",
                ))
            except sqlite3.Error as exc:
                report.add(Check(
                    "db.bridge",
                    "fail",
                    f"Cannot connect to bridge database: {exc}",
                ))
        else:
            report.add(Check(
                "db.bridge",
                "warn",
                f"Bridge database not found at {bridge_db}",
            ))


def check_wallet(report: ValidationReport) -> None:
    """Verify wallet file existence and basic validity."""
    wallet_name = os.environ.get("WALLET_NAME", "")
    if not wallet_name or wallet_name == "RTC_your_wallet_id_here":
        report.add(Check(
            "wallet.configured",
            "warn",
            "WALLET_NAME is not configured or uses the placeholder value",
        ))
    elif not wallet_name.startswith("RTC"):
        report.add(Check(
            "wallet.configured",
            "warn",
            f"WALLET_NAME='{wallet_name}' does not start with the expected 'RTC' prefix",
        ))
    else:
        report.add(Check(
            "wallet.configured",
            "pass",
            f"WALLET_NAME is set to '{wallet_name}'",
        ))

    # Look for wallet files on disk
    found_any = False
    for candidate in WALLET_DIR_CANDIDATES:
        if candidate.exists() and candidate.is_dir():
            wallet_files = list(candidate.glob("*.json")) + list(candidate.glob("*.wallet"))
            if wallet_files:
                found_any = True
                for wf in wallet_files:
                    size = wf.stat().st_size
                    if size == 0:
                        report.add(Check(
                            "wallet.file",
                            "fail",
                            f"Wallet file is empty: {wf}",
                        ))
                    elif size < 20:
                        report.add(Check(
                            "wallet.file",
                            "warn",
                            f"Wallet file suspiciously small ({size}B): {wf}",
                        ))
                    else:
                        # Try to parse as JSON
                        try:
                            data = json.loads(wf.read_text(encoding="utf-8"))
                            report.add(Check(
                                "wallet.file",
                                "pass",
                                f"Valid wallet file found: {wf.name} ({size}B)",
                                detail=f"keys={list(data.keys()) if isinstance(data, dict) else 'array'}",
                            ))
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            report.add(Check(
                                "wallet.file",
                                "warn",
                                f"Wallet file found but not valid JSON: {wf.name}",
                            ))

    if not found_any:
        report.add(Check(
            "wallet.file",
            "skip",
            "No wallet files found in standard locations",
            detail=", ".join(str(p) for p in WALLET_DIR_CANDIDATES),
        ))


def check_ssl(report: ValidationReport) -> None:
    """Validate SSL certificate configuration."""
    ssl_enabled = os.environ.get("ENABLE_SSL", "false").lower() == "true"
    if not ssl_enabled:
        report.add(Check(
            "ssl.enabled",
            "skip",
            "SSL is disabled (ENABLE_SSL != true) — skipping certificate checks",
        ))
        return

    cert_path = os.environ.get("SSL_CERT_PATH", "./ssl/cert.pem")
    key_path = os.environ.get("SSL_KEY_PATH", "./ssl/key.pem")

    # Check certificate file
    if not Path(cert_path).exists():
        report.add(Check(
            "ssl.cert",
            "fail",
            f"SSL is enabled but certificate not found at {cert_path}",
        ))
    else:
        report.add(Check(
            "ssl.cert",
            "pass",
            f"SSL certificate exists at {cert_path}",
        ))
        # Attempt to load and inspect the cert
        try:
            import ssl as _ssl
            ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
            ctx.load_cert_chain(cert_path, key_path)
            report.add(Check(
                "ssl.cert.load",
                "pass",
                "Certificate and key loaded successfully",
            ))
        except _ssl.SSLError as exc:
            report.add(Check(
                "ssl.cert.load",
                "fail",
                f"Failed to load certificate/key pair: {exc}",
            ))
        except FileNotFoundError:
            pass  # key missing — handled below
        except Exception as exc:
            report.add(Check(
                "ssl.cert.load",
                "warn",
                f"Could not verify certificate: {exc}",
            ))

        # Check expiry using openssl if available
        openssl = shutil.which("openssl")
        if openssl:
            try:
                out = subprocess.check_output(
                    [openssl, "x509", "-enddate", "-noout", "-in", cert_path],
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=10,
                )
                # Parse "notAfter=Mon DD HH:MM:SS YYYY GMT"
                date_str = out.strip().split("=", 1)[1]
                expiry = datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z")
                days_left = (expiry - datetime.now()).days
                if days_left < 0:
                    report.add(Check(
                        "ssl.cert.expiry",
                        "fail",
                        f"SSL certificate expired {abs(days_left)} days ago",
                    ))
                elif days_left < 30:
                    report.add(Check(
                        "ssl.cert.expiry",
                        "warn",
                        f"SSL certificate expires in {days_left} days — renew soon",
                    ))
                else:
                    report.add(Check(
                        "ssl.cert.expiry",
                        "pass",
                        f"SSL certificate valid for {days_left} more days",
                    ))
            except Exception:
                pass

    # Check key file
    if not Path(key_path).exists():
        report.add(Check(
            "ssl.key",
            "fail",
            f"SSL is enabled but private key not found at {key_path}",
        ))
    else:
        # Warn about permissions
        try:
            mode = oct(Path(key_path).stat().st_mode)[-3:]
            if mode not in ("600", "400"):
                report.add(Check(
                    "ssl.key.perms",
                    "warn",
                    f"Private key permissions are {mode} — recommend 600 or 400",
                ))
            else:
                report.add(Check(
                    "ssl.key.perms",
                    "pass",
                    f"Private key permissions are {mode}",
                ))
        except Exception:
            pass
        report.add(Check("ssl.key", "pass", f"SSL private key exists at {key_path}"))


def check_network(report: ValidationReport) -> None:
    """Test network connectivity to known RustChain endpoints."""
    node_url = os.environ.get("NODE_URL", "")
    targets: List[Tuple[str, int]] = list(KNOWN_ENDPOINTS)

    # Parse NODE_URL into host:port if set
    if node_url:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(node_url)
            host = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if host:
                targets.insert(0, (host, port))
        except Exception:
            pass

    if not targets:
        report.add(Check(
            "network.connectivity",
            "skip",
            "No endpoints to test",
        ))
        return

    reachable = 0
    for host, port in targets:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                s.connect((host, port))
                reachable += 1
                report.add(Check(
                    f"network.{host}:{port}",
                    "pass",
                    f"Endpoint {host}:{port} is reachable",
                ))
        except (socket.timeout, ConnectionRefusedError, OSError) as exc:
            report.add(Check(
                f"network.{host}:{port}",
                "warn",
                f"Cannot reach {host}:{port} — {exc}",
            ))

    # DNS resolution test
    try:
        addr = socket.getaddrinfo("rustchain.org", 443, socket.AF_INET)
        if addr:
            report.add(Check(
                "network.dns",
                "pass",
                f"DNS resolution working (rustchain.org -> {addr[0][4][0]})",
            ))
    except socket.gaierror as exc:
        report.add(Check(
            "network.dns",
            "warn",
            f"DNS resolution failed for rustchain.org: {exc}",
        ))


def check_directories(report: ValidationReport) -> None:
    """Verify required directories exist and are writable."""
    rustchain_home = os.environ.get("RUSTCHAIN_HOME", "")
    download_dir = os.environ.get("DOWNLOAD_DIR", "")

    for label, path in [("RUSTCHAIN_HOME", rustchain_home), ("DOWNLOAD_DIR", download_dir)]:
        if not path:
            continue
        p = Path(path)
        if not p.exists():
            report.add(Check(
                f"dir.{label}",
                "warn",
                f"{label} directory does not exist: {path}",
            ))
        elif not os.access(str(p), os.W_OK):
            report.add(Check(
                f"dir.{label}",
                "fail",
                f"{label} directory is not writable: {path}",
            ))
        else:
            report.add(Check(
                f"dir.{label}",
                "pass",
                f"{label} directory exists and is writable",
                detail=f"path={path}",
            ))


def recommend_settings(report: ValidationReport) -> None:
    """Suggest optimal configuration values based on detected hardware."""
    try:
        cpu_count = os.cpu_count() or 1
    except Exception:
        cpu_count = 1

    mem_bytes = _get_total_memory()
    mem_gb = mem_bytes / (1024 ** 3) if mem_bytes else 0

    report.recommendations.append(
        f"Detected {cpu_count} CPU core(s), {mem_gb:.1f} GB RAM"
    )

    # Docker resource limits
    if mem_gb >= 8:
        rec_mem = "2g"
        rec_cpus = min(cpu_count, 4)
    elif mem_gb >= 4:
        rec_mem = "1g"
        rec_cpus = min(cpu_count, 2)
    else:
        rec_mem = "512m"
        rec_cpus = 1

    report.recommendations.append(
        f"Recommended Docker limits: RUSTCHAIN_NODE_MEMORY={rec_mem}, "
        f"RUSTCHAIN_NODE_CPUS={rec_cpus}"
    )

    # Log level
    current_log = os.environ.get("LOG_LEVEL", "INFO")
    if current_log == "DEBUG" and mem_gb < 4:
        report.recommendations.append(
            "Consider LOG_LEVEL=INFO on low-memory systems to reduce I/O"
        )

    # Block time sanity
    try:
        block_time = int(os.environ.get("BLOCK_TIME", "600"))
        if block_time != 600:
            report.recommendations.append(
                f"BLOCK_TIME={block_time}s differs from network default (600s) "
                "— ensure this is intentional"
            )
    except ValueError:
        pass

    # Database location
    db_path = os.environ.get("RUSTCHAIN_DB", "")
    if db_path:
        disk = _get_disk_free(Path(db_path).parent)
        if disk is not None:
            disk_gb = disk / (1024 ** 3)
            report.recommendations.append(
                f"Free disk space at DB location: {disk_gb:.1f} GB"
            )
            if disk_gb < 1:
                report.recommendations.append(
                    "WARNING: Less than 1 GB free — consider expanding storage"
                )

    # SSL recommendation
    if os.environ.get("ENABLE_SSL", "false").lower() != "true":
        report.recommendations.append(
            "SSL is disabled. For production deployments, enable SSL with "
            "ENABLE_SSL=true and provide valid certificates."
        )

    # Non-root check
    if os.environ.get("RUN_AS_NON_ROOT", "false").lower() != "true":
        report.recommendations.append(
            "Set RUN_AS_NON_ROOT=true for improved container security"
        )


def _get_total_memory() -> int:
    """Return total physical memory in bytes, or 0 on failure."""
    system = platform.system()
    try:
        if system == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) * 1024
        elif system == "Darwin":
            out = subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"], text=True, timeout=5
            )
            return int(out.strip())
        elif system == "Windows":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return stat.ullTotalPhys
    except Exception:
        pass
    return 0


def _get_disk_free(path: Path) -> Optional[int]:
    """Return free bytes at *path*, or None on failure."""
    try:
        usage = shutil.disk_usage(str(path))
        return usage.free
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

_STATUS_ICON = {
    "pass": "[PASS]",
    "warn": "[WARN]",
    "fail": "[FAIL]",
    "skip": "[SKIP]",
}


def print_report(report: ValidationReport) -> None:
    """Pretty-print the validation report to stdout."""
    width = 72
    print("=" * width)
    print("  RustChain Node Configuration Validator")
    print("=" * width)
    print()

    for check in report.checks:
        icon = _STATUS_ICON.get(check.status, "[ ?? ]")
        print(f"  {icon}  {check.message}")
        if check.detail:
            for line in textwrap.wrap(check.detail, width - 14):
                print(f"              {line}")

    print()
    print("-" * width)
    print(
        f"  Result: {report.overall}  |  "
        f"Passed: {report.passed}  Warnings: {report.warnings}  "
        f"Failures: {report.failures}  Skipped: {report.skipped}"
    )
    print("-" * width)

    if report.recommendations:
        print()
        print("  Recommendations:")
        for rec in report.recommendations:
            print(f"    - {rec}")

    print()


# ---------------------------------------------------------------------------
# .env file loader
# ---------------------------------------------------------------------------

def load_dotenv(path: Optional[str] = None) -> None:
    """Load a .env file into os.environ (simple key=value parser)."""
    candidates = [path] if path else [
        ".env",
        os.path.join(os.environ.get("RUSTCHAIN_HOME", ""), ".env"),
        os.path.join(Path.home(), ".rustchain", ".env"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            with open(candidate) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        os.environ.setdefault(key, value)
            break


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate RustChain node configuration"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output results as JSON"
    )
    parser.add_argument(
        "--env-file", type=str, default=None,
        help="Path to .env file to load before validation"
    )
    parser.add_argument(
        "--fix", action="store_true",
        help="Attempt to auto-create missing directories"
    )
    args = parser.parse_args()

    # Load .env
    load_dotenv(args.env_file)

    # Auto-fix: create missing directories
    if args.fix:
        for var in ("RUSTCHAIN_HOME", "DOWNLOAD_DIR"):
            val = os.environ.get(var)
            if val and not Path(val).exists():
                try:
                    Path(val).mkdir(parents=True, exist_ok=True)
                    print(f"  Created directory: {val}")
                except OSError as exc:
                    print(f"  Could not create {val}: {exc}")

    report = ValidationReport()

    check_required_env(report)
    check_port_ranges(report)
    check_database(report)
    check_wallet(report)
    check_ssl(report)
    check_network(report)
    check_directories(report)
    recommend_settings(report)

    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        print_report(report)

    return 0 if report.failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
