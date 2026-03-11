#!/usr/bin/env python3
"""
RustChain Node Health Monitor CLI

A command-line tool to monitor RustChain node health with comprehensive checks
for health status, epoch information, and peer/API reachability.

Exit codes:
    0 - All checks passed
    1 - Health check failed (node unhealthy or unreachable)
    2 - Epoch check failed (epoch data unavailable or inconsistent)
    3 - Peer/API reachability check failed
    4 - Multiple checks failed
"""

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


# Exit codes
EXIT_OK = 0
EXIT_HEALTH_FAIL = 1
EXIT_EPOCH_FAIL = 2
EXIT_REACHABILITY_FAIL = 3
EXIT_MULTI_FAIL = 4

# Default configuration
DEFAULT_NODE_URL = "https://rustchain.org"
DEFAULT_TIMEOUT = 10
DEFAULT_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0


@dataclass
class HealthStatus:
    """Node health status"""
    ok: bool
    version: Optional[str]
    uptime_s: Optional[int]
    db_rw: Optional[bool]
    backup_age_hours: Optional[float]
    tip_age_slots: Optional[int]
    error: Optional[str]


@dataclass
class EpochStatus:
    """Epoch information"""
    epoch: Optional[int]
    slot: Optional[int]
    epoch_pot: Optional[float]
    enrolled_miners: Optional[int]
    blocks_per_epoch: Optional[int]
    total_supply_rtc: Optional[float]
    error: Optional[str]


@dataclass
class ReachabilityStatus:
    """API endpoint reachability"""
    endpoint: str
    reachable: bool
    latency_ms: Optional[float]
    status_code: Optional[int]
    error: Optional[str]


@dataclass
class CheckResult:
    """Overall check result"""
    node_url: str
    timestamp: str
    health: HealthStatus
    epoch: EpochStatus
    reachability: List[ReachabilityStatus]
    overall_ok: bool
    exit_code: int


def fetch_json(url: str, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """Fetch JSON data from URL with retry logic"""
    last_error = None
    
    for attempt in range(DEFAULT_RETRIES):
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
            return json.loads(payload)
        except HTTPError as e:
            last_error = f"HTTP {e.code}: {e.reason}"
            time.sleep(DEFAULT_RETRY_DELAY)
        except URLError as e:
            last_error = f"Connection error: {e.reason}"
            time.sleep(DEFAULT_RETRY_DELAY)
        except json.JSONDecodeError as e:
            last_error = f"JSON parse error: {e}"
            break
        except Exception as e:
            last_error = f"Unexpected error: {e}"
            time.sleep(DEFAULT_RETRY_DELAY)
    
    raise Exception(last_error or "Unknown error")


def check_health(node_url: str, timeout: int) -> HealthStatus:
    """Check node health status"""
    try:
        url = f"{node_url.rstrip('/')}/health"
        data = fetch_json(url, timeout)
        
        return HealthStatus(
            ok=bool(data.get("ok", False)),
            version=data.get("version"),
            uptime_s=data.get("uptime_s"),
            db_rw=data.get("db_rw"),
            backup_age_hours=data.get("backup_age_hours"),
            tip_age_slots=data.get("tip_age_slots"),
            error=None
        )
    except Exception as e:
        return HealthStatus(
            ok=False,
            version=None,
            uptime_s=None,
            db_rw=None,
            backup_age_hours=None,
            tip_age_slots=None,
            error=str(e)
        )


def check_epoch(node_url: str, timeout: int) -> EpochStatus:
    """Check current epoch information"""
    try:
        url = f"{node_url.rstrip('/')}/epoch"
        data = fetch_json(url, timeout)
        
        return EpochStatus(
            epoch=data.get("epoch"),
            slot=data.get("slot"),
            epoch_pot=data.get("epoch_pot"),
            enrolled_miners=data.get("enrolled_miners"),
            blocks_per_epoch=data.get("blocks_per_epoch"),
            total_supply_rtc=data.get("total_supply_rtc"),
            error=None
        )
    except Exception as e:
        return EpochStatus(
            epoch=None,
            slot=None,
            epoch_pot=None,
            enrolled_miners=None,
            blocks_per_epoch=None,
            total_supply_rtc=None,
            error=str(e)
        )


def check_reachability(node_url: str, endpoints: List[str], timeout: int) -> List[ReachabilityStatus]:
    """Check API endpoint reachability"""
    results = []
    base_url = node_url.rstrip('/')
    
    for endpoint in endpoints:
        url = f"{base_url}{endpoint}"
        start_time = time.time()
        
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=timeout) as response:
                latency_ms = (time.time() - start_time) * 1000
                results.append(ReachabilityStatus(
                    endpoint=endpoint,
                    reachable=True,
                    latency_ms=round(latency_ms, 2),
                    status_code=response.status,
                    error=None
                ))
        except HTTPError as e:
            latency_ms = (time.time() - start_time) * 1000
            results.append(ReachabilityStatus(
                endpoint=endpoint,
                reachable=False,
                latency_ms=round(latency_ms, 2),
                status_code=e.code,
                error=f"HTTP {e.code}"
            ))
        except URLError as e:
            latency_ms = (time.time() - start_time) * 1000
            results.append(ReachabilityStatus(
                endpoint=endpoint,
                reachable=False,
                latency_ms=round(latency_ms, 2),
                status_code=None,
                error=str(e.reason)
            ))
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            results.append(ReachabilityStatus(
                endpoint=endpoint,
                reachable=False,
                latency_ms=round(latency_ms, 2),
                status_code=None,
                error=str(e)
            ))
    
    return results


def run_checks(node_url: str, timeout: int, custom_endpoints: Optional[List[str]] = None) -> CheckResult:
    """Run all health checks"""
    default_endpoints = ["/health", "/epoch", "/api/miners"]
    endpoints = custom_endpoints if custom_endpoints else default_endpoints
    
    health = check_health(node_url, timeout)
    epoch = check_epoch(node_url, timeout)
    reachability = check_reachability(node_url, endpoints, timeout)
    
    # Determine overall status and exit code
    health_ok = health.ok and health.error is None
    epoch_ok = epoch.epoch is not None and epoch.error is None
    reachability_ok = all(r.reachable for r in reachability)
    
    failures = []
    if not health_ok:
        failures.append("health")
    if not epoch_ok:
        failures.append("epoch")
    if not reachability_ok:
        failures.append("reachability")
    
    overall_ok = len(failures) == 0
    
    # Determine exit code
    if len(failures) == 0:
        exit_code = EXIT_OK
    elif len(failures) >= 2:
        exit_code = EXIT_MULTI_FAIL
    elif "health" in failures:
        exit_code = EXIT_HEALTH_FAIL
    elif "epoch" in failures:
        exit_code = EXIT_EPOCH_FAIL
    elif "reachability" in failures:
        exit_code = EXIT_REACHABILITY_FAIL
    else:
        exit_code = EXIT_MULTI_FAIL
    
    return CheckResult(
        node_url=node_url,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        health=health,
        epoch=epoch,
        reachability=reachability,
        overall_ok=overall_ok,
        exit_code=exit_code
    )


def format_text(result: CheckResult, verbose: bool = False) -> str:
    """Format result as human-readable text"""
    lines = []
    
    # Header
    lines.append("=" * 60)
    lines.append("RustChain Node Health Check")
    lines.append("=" * 60)
    lines.append(f"Node URL: {result.node_url}")
    lines.append(f"Timestamp: {result.timestamp}")
    lines.append("")
    
    # Health status
    health_icon = "✓" if result.health.ok else "✗"
    lines.append(f"[{health_icon}] Health Status")
    if result.health.error:
        lines.append(f"    Error: {result.health.error}")
    else:
        lines.append(f"    OK: {result.health.ok}")
        lines.append(f"    Version: {result.health.version or 'N/A'}")
        lines.append(f"    Uptime: {format_uptime(result.health.uptime_s)}")
        lines.append(f"    DB Read/Write: {'OK' if result.health.db_rw else 'FAIL'}")
        if verbose and result.health.backup_age_hours is not None:
            lines.append(f"    Backup Age: {result.health.backup_age_hours:.1f} hours")
        if verbose and result.health.tip_age_slots is not None:
            lines.append(f"    Tip Age: {result.health.tip_age_slots} slots")
    lines.append("")
    
    # Epoch status
    epoch_icon = "✓" if result.epoch.epoch is not None else "✗"
    lines.append(f"[{epoch_icon}] Epoch Information")
    if result.epoch.error:
        lines.append(f"    Error: {result.epoch.error}")
    else:
        lines.append(f"    Epoch: {result.epoch.epoch}")
        lines.append(f"    Slot: {result.epoch.slot}")
        lines.append(f"    Epoch Pot: {result.epoch.epoch_pot} RTC")
        lines.append(f"    Enrolled Miners: {result.epoch.enrolled_miners}")
        lines.append(f"    Total Supply: {result.epoch.total_supply_rtc} RTC")
    lines.append("")
    
    # Reachability status
    lines.append("[✓] API Reachability" if all(r.reachable for r in result.reachability) else "[✗] API Reachability")
    for r in result.reachability:
        status_icon = "✓" if r.reachable else "✗"
        latency = f"{r.latency_ms:.0f}ms" if r.latency_ms else "N/A"
        status = f"{status_icon} {r.endpoint}: {latency}"
        if r.status_code:
            status += f" (HTTP {r.status_code})"
        if r.error:
            status += f" - {r.error}"
        lines.append(f"    {status}")
    lines.append("")
    
    # Summary
    lines.append("-" * 60)
    if result.overall_ok:
        lines.append("STATUS: ALL CHECKS PASSED")
    else:
        lines.append("STATUS: CHECKS FAILED")
        if not result.health.ok:
            lines.append("  - Health check failed")
        if result.epoch.epoch is None:
            lines.append("  - Epoch check failed")
        if not all(r.reachable for r in result.reachability):
            lines.append("  - Reachability check failed")
    lines.append(f"EXIT CODE: {result.exit_code}")
    lines.append("=" * 60)
    
    return "\n".join(lines)


def format_json(result: CheckResult) -> str:
    """Format result as JSON"""
    data = {
        "node_url": result.node_url,
        "timestamp": result.timestamp,
        "health": asdict(result.health),
        "epoch": asdict(result.epoch),
        "reachability": [asdict(r) for r in result.reachability],
        "overall_ok": result.overall_ok,
        "exit_code": result.exit_code
    }
    return json.dumps(data, indent=2)


def format_uptime(seconds: Optional[int]) -> str:
    """Format uptime in human-readable format"""
    if seconds is None:
        return "N/A"
    
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or not parts:
        parts.append(f"{minutes}m")
    
    return " ".join(parts)


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        prog="node-health",
        description="RustChain Node Health Monitor - Check node health, epoch info, and API reachability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Codes:
  0  All checks passed
  1  Health check failed
  2  Epoch check failed
  3  API reachability check failed
  4  Multiple checks failed

Examples:
  %(prog)s                              # Check default node (rustchain.org)
  %(prog)s -n http://localhost:8099     # Check local node
  %(prog)s --json                       # Output as JSON
  %(prog)s -v                           # Verbose output
  %(prog)s -e /health /epoch            # Check specific endpoints
        """
    )
    
    parser.add_argument(
        "-n", "--node",
        default=DEFAULT_NODE_URL,
        help=f"Node URL to check (default: {DEFAULT_NODE_URL})"
    )
    
    parser.add_argument(
        "-t", "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT})"
    )
    
    parser.add_argument(
        "-e", "--endpoints",
        nargs="+",
        help="Custom endpoints to check reachability (default: /health /epoch /api/miners /ready)"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output with additional details"
    )
    
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Quiet mode - only output exit code"
    )
    
    return parser.parse_args(args)


def main(args: Optional[List[str]] = None) -> int:
    """Main entry point"""
    parsed_args = parse_args(args)
    
    # Run health checks
    result = run_checks(
        node_url=parsed_args.node,
        timeout=parsed_args.timeout,
        custom_endpoints=parsed_args.endpoints
    )
    
    # Output results
    if not parsed_args.quiet:
        if parsed_args.json:
            print(format_json(result))
        else:
            print(format_text(result, verbose=parsed_args.verbose))
    
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
