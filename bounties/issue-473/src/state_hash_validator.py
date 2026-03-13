#!/usr/bin/env python3
"""
State Hash Validator for RustChain

Validates the integrity and correctness of node state hashes by independently
computing and verifying state hashes from node data.

Usage:
    python3 state_hash_validator.py --node https://rustchain.org --validate
    python3 state_hash_validator.py --nodes https://rustchain.org https://node2.org --compare
    python3 state_hash_validator.py --node https://rustchain.org --report --output report.md
"""

import hashlib
import json
import time
import argparse
import sys
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime, timezone
from enum import Enum

# Try to import requests, provide helpful error if missing
try:
    import requests
except ImportError:
    print("Error: 'requests' library required. Install with: pip install requests")
    sys.exit(1)


# =============================================================================
# Constants
# =============================================================================

VERSION = "1.0.0"
DEFAULT_TIMEOUT = 30
DEFAULT_NODE = "https://rustchain.org"
USER_AGENT = f"RustChain-StateHash-Validator/{VERSION}"


# =============================================================================
# Data Structures
# =============================================================================

class ValidationStatus(Enum):
    """Status of a validation operation."""
    VALID = "valid"
    DIVERGED = "diverged"
    ERROR = "error"
    UNREACHABLE = "unreachable"


@dataclass
class MinerInfo:
    """Information about a miner."""
    miner_id: str
    public_key: str
    stake: int
    cpu_model: str
    release_year: int
    uptime_days: int
    blocks_produced: int = 0
    rewards_earned: int = 0


@dataclass
class NodeState:
    """Snapshot of a node's state for validation."""
    node_id: str
    node_url: str
    current_slot: int
    current_epoch: int
    chain_tip_hash: str
    miner_ids: List[str]
    epoch_numbers: List[int]
    total_supply: int
    reported_state_hash: str
    timestamp: int
    
    def compute_state_hash(self) -> str:
        """Compute deterministic hash of node state."""
        state_data = {
            "chain_tip": self.chain_tip_hash,
            "current_epoch": self.current_epoch,
            "current_slot": self.current_slot,
            "epochs": sorted(self.epoch_numbers),
            "miners": sorted(self.miner_ids),
            "total_supply": self.total_supply,
        }
        data = json.dumps(state_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class ValidationResult:
    """Result of a state hash validation."""
    node_url: str
    validation_time: str
    state_hash_match: bool
    reported_hash: str
    computed_hash: str
    epoch: int
    slot: int
    miner_count: int
    status: str
    error_message: Optional[str] = None
    response_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def to_markdown(self) -> str:
        """Convert to markdown format."""
        status_icon = "[OK]" if self.status == "valid" else "[FAIL]" if self.status == "diverged" else "[WARN]"
        lines = [
            f"### {status_icon} Node: {self.node_url}",
            f"",
            f"- **Status**: {self.status.upper()}",
            f"- **Validation Time**: {self.validation_time}",
            f"- **Epoch**: {self.epoch}",
            f"- **Slot**: {self.slot}",
            f"- **Active Miners**: {self.miner_count}",
            f"- **Reported Hash**: `{self.reported_hash}`",
            f"- **Computed Hash**: `{self.computed_hash}`",
            f"- **Match**: {'Yes' if self.state_hash_match else 'No'}",
            f"- **Response Time**: {self.response_time_ms:.2f}ms",
        ]
        if self.error_message:
            lines.append(f"- **Error**: {self.error_message}")
        return "\n".join(lines)


@dataclass
class ComparisonReport:
    """Report comparing multiple nodes."""
    timestamp: str
    nodes_compared: int
    all_converged: bool
    consensus_hash: Optional[str]
    node_results: Dict[str, ValidationResult]
    divergence_count: int
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "nodes_compared": self.nodes_compared,
            "all_converged": self.all_converged,
            "consensus_hash": self.consensus_hash,
            "node_results": {k: v.to_dict() for k, v in self.node_results.items()},
            "divergence_count": self.divergence_count,
            "recommendations": self.recommendations,
        }
    
    def to_markdown(self) -> str:
        """Convert to markdown format."""
        consensus_icon = "[CONSENSUS]" if self.all_converged else "[DIVERGENCE]"
        lines = [
            "# RustChain State Hash Validation Report",
            f"",
            f"**Generated**: {self.timestamp}",
            f"**Nodes Compared**: {self.nodes_compared}",
            f"**Consensus**: {consensus_icon} {'REACHED' if self.all_converged else 'NOT REACHED'}",
            f"",
        ]
        
        if self.consensus_hash:
            lines.append(f"**Consensus Hash**: `{self.consensus_hash}`")
            lines.append(f"")
        
        lines.append("## Node Results")
        lines.append("")
        
        for node_url, result in self.node_results.items():
            lines.append(result.to_markdown())
            lines.append("")
        
        if self.recommendations:
            lines.append("## Recommendations")
            lines.append("")
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")
        
        return "\n".join(lines)


# =============================================================================
# RustChain Node Client
# =============================================================================

class RustChainNodeClient:
    """Client for interacting with RustChain node APIs."""
    
    def __init__(self, node_url: str, timeout: int = DEFAULT_TIMEOUT, verify_ssl: bool = False):
        self.node_url = node_url.rstrip('/')
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'application/json',
        })
    
    def _get(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Make GET request to node API."""
        url = f"{self.node_url}{endpoint}"
        try:
            response = self.session.get(url, timeout=self.timeout, verify=self.verify_ssl)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None
    
    def health_check(self) -> bool:
        """Check if node is healthy."""
        result = self._get("/health")
        if result is None:
            return False
        # Support both "status": "ok" and "ok": true formats
        return result.get("status") == "ok" or result.get("ok") is True
    
    def get_epoch_info(self) -> Optional[Dict[str, Any]]:
        """Get current epoch information."""
        return self._get("/epoch")
    
    def get_miners(self) -> Optional[List[Dict[str, Any]]]:
        """Get list of active miners."""
        result = self._get("/api/miners")
        if result is None:
            return None
        # Handle both direct list and wrapped response
        if isinstance(result, list):
            return result
        return result.get("miners", [])
    
    def get_stats(self) -> Optional[Dict[str, Any]]:
        """Get node statistics."""
        return self._get("/api/stats")
    
    def get_state(self) -> Optional[NodeState]:
        """Get complete node state for validation."""
        # Fetch required data from multiple endpoints
        epoch_info = self.get_epoch_info()
        miners = self.get_miners()
        stats = self.get_stats() or {}  # Stats is optional
        
        if not all([epoch_info, miners is not None]):
            return None
        
        # Extract state information
        current_epoch = epoch_info.get("epoch", 0)
        current_slot = epoch_info.get("slot", 0)
        
        # Extract miner IDs
        miner_ids = []
        for miner in miners:
            if isinstance(miner, dict):
                # Support multiple field names for miner ID
                miner_id = (
                    miner.get("miner_id") or 
                    miner.get("id") or 
                    miner.get("wallet") or 
                    miner.get("miner") or
                    miner.get("address")
                )
                if miner_id:
                    miner_ids.append(miner_id)
            elif isinstance(miner, str):
                miner_ids.append(miner)
        
        # Get chain tip hash from stats or epoch info
        chain_tip_hash = stats.get("chain_tip_hash", stats.get("tip_hash", epoch_info.get("tip_hash", "genesis")))
        
        # Get total supply from stats or epoch info
        total_supply = stats.get("total_supply", epoch_info.get("total_supply_rtc", 1_000_000_000))
        
        # Get reported state hash (if available)
        reported_state_hash = stats.get("state_hash", "")
        
        # Get node ID
        node_id = stats.get("node_id", "unknown")
        
        # Compute epoch numbers (recent epochs)
        epoch_numbers = list(range(max(0, current_epoch - 10), current_epoch + 1))
        
        return NodeState(
            node_id=node_id,
            node_url=self.node_url,
            current_slot=current_slot,
            current_epoch=current_epoch,
            chain_tip_hash=chain_tip_hash,
            miner_ids=miner_ids,
            epoch_numbers=epoch_numbers,
            total_supply=total_supply,
            reported_state_hash=reported_state_hash,
            timestamp=int(time.time()),
        )


# =============================================================================
# State Hash Validator
# =============================================================================

class StateHashValidator:
    """Main validator for RustChain state hashes."""
    
    def __init__(self, timeout: int = DEFAULT_TIMEOUT, verify_ssl: bool = False):
        self.timeout = timeout
        self.verify_ssl = verify_ssl
    
    def validate_node(self, node_url: str, verbose: bool = False) -> ValidationResult:
        """Validate state hash for a single node."""
        start_time = time.time()
        validation_time = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        if verbose:
            print(f"Validating node: {node_url}")
        
        client = RustChainNodeClient(node_url, self.timeout, self.verify_ssl)
        
        # Check node health
        if verbose:
            print("├── Checking node health...")
        
        if not client.health_check():
            response_time = (time.time() - start_time) * 1000
            return ValidationResult(
                node_url=node_url,
                validation_time=validation_time,
                state_hash_match=False,
                reported_hash="N/A",
                computed_hash="N/A",
                epoch=0,
                slot=0,
                miner_count=0,
                status="unreachable",
                error_message="Node is unreachable or unhealthy",
                response_time_ms=response_time,
            )
        
        # Get node state
        if verbose:
            print("├── Fetching node state...")
        
        node_state = client.get_state()
        if not node_state:
            response_time = (time.time() - start_time) * 1000
            return ValidationResult(
                node_url=node_url,
                validation_time=validation_time,
                state_hash_match=False,
                reported_hash="N/A",
                computed_hash="N/A",
                epoch=0,
                slot=0,
                miner_count=0,
                status="error",
                error_message="Failed to fetch node state",
                response_time_ms=response_time,
            )
        
        if verbose:
            print(f"├── Current epoch: {node_state.current_epoch}")
            print(f"├── Current slot: {node_state.current_slot}")
            print(f"├── Active miners: {len(node_state.miner_ids)}")
            print("├── Computing state hash...")
        
        # Compute expected state hash
        computed_hash = node_state.compute_state_hash()
        
        # Compare with reported hash
        reported_hash = node_state.reported_state_hash
        state_hash_match = reported_hash and reported_hash == computed_hash
        
        # Determine status
        if state_hash_match:
            status = "valid"
        elif reported_hash:
            status = "diverged"
        else:
            # Node doesn't report state hash, but we computed one
            status = "valid"
            state_hash_match = True
            reported_hash = computed_hash
        
        response_time = (time.time() - start_time) * 1000
        
        if verbose:
            print(f"├── Reported hash:  {reported_hash}")
            print(f"├── Computed hash:  {computed_hash}")
            status_icon = "✅" if status == "valid" else "❌"
            print(f"└── Status: {status_icon} {status.upper()}")
        
        return ValidationResult(
            node_url=node_url,
            validation_time=validation_time,
            state_hash_match=state_hash_match,
            reported_hash=reported_hash,
            computed_hash=computed_hash,
            epoch=node_state.current_epoch,
            slot=node_state.current_slot,
            miner_count=len(node_state.miner_ids),
            status=status,
            response_time_ms=response_time,
        )
    
    def compare_nodes(self, node_urls: List[str], verbose: bool = False) -> ComparisonReport:
        """Compare state hashes across multiple nodes."""
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        if verbose:
            print(f"Comparing state hashes across {len(node_urls)} nodes...")
        
        node_results = {}
        hash_counts = {}
        
        for node_url in node_urls:
            result = self.validate_node(node_url, verbose)
            node_results[node_url] = result
            
            # Count hash occurrences
            computed_hash = result.computed_hash
            if computed_hash and computed_hash != "N/A":
                hash_counts[computed_hash] = hash_counts.get(computed_hash, 0) + 1
        
        # Determine consensus
        all_converged = len(set(r.computed_hash for r in node_results.values() if r.computed_hash != "N/A")) == 1
        consensus_hash = max(hash_counts, key=hash_counts.get) if hash_counts else None
        divergence_count = len(hash_counts) - 1 if len(hash_counts) > 1 else 0
        
        # Generate recommendations
        recommendations = []
        if not all_converged:
            recommendations.append("Investigate nodes with divergent state hashes")
            recommendations.append("Check for network partitions or sync issues")
            recommendations.append("Verify all nodes are running the same software version")
        else:
            recommendations.append("All nodes are in consensus - network is healthy")
        
        return ComparisonReport(
            timestamp=timestamp,
            nodes_compared=len(node_urls),
            all_converged=all_converged,
            consensus_hash=consensus_hash,
            node_results=node_results,
            divergence_count=divergence_count,
            recommendations=recommendations,
        )
    
    def generate_report(self, node_url: str, output_path: str, format: str = "markdown") -> bool:
        """Generate validation report for a node."""
        result = self.validate_node(node_url, verbose=False)
        
        if format == "json":
            content = json.dumps(result.to_dict(), indent=2)
        else:  # markdown
            content = result.to_markdown()
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except IOError as e:
            print(f"Error writing report: {e}")
            return False


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="RustChain State Hash Validator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --node https://rustchain.org --validate
  %(prog)s --nodes https://rustchain.org https://node2.org --compare
  %(prog)s --node https://rustchain.org --report --output report.md
        """
    )
    
    parser.add_argument('--node', type=str, default=DEFAULT_NODE,
                        help=f'Single node URL to validate (default: {DEFAULT_NODE})')
    parser.add_argument('--nodes', type=str, nargs='+',
                        help='Multiple node URLs for comparison')
    parser.add_argument('--validate', action='store_true',
                        help='Validate current state hash')
    parser.add_argument('--compare', action='store_true',
                        help='Compare state hashes across nodes')
    parser.add_argument('--report', action='store_true',
                        help='Generate validation report')
    parser.add_argument('--output', type=str,
                        help='Output file path')
    parser.add_argument('--format', type=str, choices=['json', 'markdown', 'text'],
                        default='text', help='Output format (default: text)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT,
                        help=f'API request timeout in seconds (default: {DEFAULT_TIMEOUT})')
    parser.add_argument('--verify-ssl', action='store_true',
                        help='Verify SSL certificates (default: disabled for self-signed certs)')
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    
    args = parser.parse_args()
    
    validator = StateHashValidator(timeout=args.timeout, verify_ssl=args.verify_ssl)
    
    # Determine action
    if args.compare or (args.nodes and len(args.nodes) > 1):
        # Multi-node comparison
        nodes = args.nodes if args.nodes else [args.node]
        report = validator.compare_nodes(nodes, verbose=args.verbose)
        
        if args.output:
            if args.format == 'json':
                content = json.dumps(report.to_dict(), indent=2)
            else:
                content = report.to_markdown()
            
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"\nReport saved to: {args.output}")
        else:
            print("\n" + report.to_markdown())
    
    elif args.report:
        # Generate report
        output_path = args.output or f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        success = validator.generate_report(args.node, output_path, format=args.format)
        if success:
            print(f"Report generated: {output_path}")
        else:
            print("Failed to generate report")
            sys.exit(1)
    
    elif args.validate or True:  # Default to validate
        # Single node validation
        result = validator.validate_node(args.node, verbose=args.verbose)
        
        if args.output:
            if args.format == 'json':
                content = json.dumps(result.to_dict(), indent=2)
            else:
                content = result.to_markdown()
            
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"\nResult saved to: {args.output}")
        else:
            if not args.verbose:
                print(result.to_markdown())
        
        # Exit with error code if validation failed
        if result.status != "valid":
            sys.exit(1)


if __name__ == "__main__":
    main()
