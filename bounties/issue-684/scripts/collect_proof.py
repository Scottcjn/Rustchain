#!/usr/bin/env python3
"""
RIP-302 Proof Collection Script

This script collects and packages evidence from challenge runs into
a verifiable proof bundle suitable for bounty submissions.

Usage:
    python collect_proof.py --output proof.json
    python collect_proof.py --evidence-dir evidence/ --output proof_bundle.json
    python collect_proof.py --include-metadata --output proof_with_meta.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("rip302_proof")

# ============================================================================
# Utilities
# ============================================================================

def blake2b_hash(data: Any) -> str:
    """Compute blake2b hash of JSON-serialized data."""
    if isinstance(data, (dict, list)):
        serialized = json.dumps(data, sort_keys=True, separators=(',', ':'))
    else:
        serialized = str(data)
    return hashlib.blake2b(serialized.encode(), digest_size=32).hexdigest()


def iso_timestamp() -> str:
    """Get current ISO 8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


def get_environment_metadata() -> Dict[str, Any]:
    """Collect environment metadata for reproducibility."""
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "timestamp": iso_timestamp(),
        "cwd": str(Path.cwd()),
        "script_path": str(Path(__file__).resolve()),
    }


def get_dependency_versions() -> Dict[str, str]:
    """Collect versions of key dependencies."""
    versions = {}
    
    try:
        import beacon_skill
        versions["beacon-skill"] = getattr(beacon_skill, '__version__', 'unknown')
    except ImportError:
        versions["beacon-skill"] = "not_installed"
    
    try:
        import grazer_skill
        versions["grazer-skill"] = getattr(grazer_skill, '__version__', 'unknown')
    except ImportError:
        versions["grazer-skill"] = "not_installed"
    
    try:
        import pytest
        versions["pytest"] = getattr(pytest, '__version__', 'unknown')
    except ImportError:
        versions["pytest"] = "not_installed"
    
    return versions


# ============================================================================
# Proof Collection
# ============================================================================

class ProofCollector:
    """Collects and packages RIP-302 challenge proof."""
    
    def __init__(self, evidence_dir: Path):
        self.evidence_dir = evidence_dir
        self.results: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}
    
    def load_results(self, result_files: Optional[List[Path]] = None) -> int:
        """Load result files from evidence directory."""
        if result_files:
            files = result_files
        else:
            files = sorted(self.evidence_dir.glob("result_*.json"))
        
        for file in files:
            try:
                with open(file) as f:
                    data = json.load(f)
                self.results.append(data)
                log.info(f"Loaded result: {file.name}")
            except Exception as e:
                log.error(f"Failed to load {file.name}: {e}")
        
        return len(self.results)
    
    def collect_metadata(self, include_full: bool = False) -> Dict[str, Any]:
        """Collect metadata about the proof collection."""
        self.metadata = {
            "collected_at": iso_timestamp(),
            "evidence_dir": str(self.evidence_dir),
            "results_count": len(self.results),
            "environment": get_environment_metadata(),
            "dependencies": get_dependency_versions()
        }
        
        if include_full:
            # Include git info if available
            try:
                import subprocess
                git_commit = subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.evidence_dir.parent,
                    stderr=subprocess.DEVNULL
                ).decode().strip()
                git_branch = subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=self.evidence_dir.parent,
                    stderr=subprocess.DEVNULL
                ).decode().strip()
                self.metadata["git"] = {
                    "commit": git_commit,
                    "branch": git_branch
                }
            except Exception:
                self.metadata["git"] = {"commit": "unknown", "branch": "unknown"}
        
        return self.metadata
    
    def compute_proof_digest(self) -> str:
        """Compute aggregate proof digest."""
        # Sort results by run_id for deterministic ordering
        sorted_results = sorted(self.results, key=lambda r: r.get("run_id", ""))
        
        # Combine all evidence digests
        digests = []
        for result in sorted_results:
            digest = result.get("final_state", {}).get("evidence_digest", "")
            if digest:
                digests.append(digest)
        
        combined = "|".join(digests)
        return blake2b_hash(combined)
    
    def build_proof_bundle(self, include_metadata: bool = True) -> Dict[str, Any]:
        """Build the complete proof bundle."""
        proof_digest = self.compute_proof_digest()
        
        bundle = {
            "rip": "RIP-302",
            "challenge_type": "Agent-to-Agent Transaction Test",
            "proof_digest": proof_digest,
            "results": self.results,
        }
        
        if include_metadata:
            bundle["metadata"] = self.collect_metadata(include_full=True)
        
        # Add summary
        bundle["summary"] = {
            "total_scenarios": len(self.results),
            "scenarios": [r.get("scenario", "unknown") for r in self.results],
            "total_steps": sum(len(r.get("steps", [])) for r in self.results),
            "all_completed": all(
                r.get("final_state", {}).get("status") == "completed"
                for r in self.results
            ),
            "proof_digest": proof_digest
        }
        
        return bundle
    
    def save_proof(self, output_path: Path, include_metadata: bool = True) -> Path:
        """Save proof bundle to file."""
        bundle = self.build_proof_bundle(include_metadata)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(bundle, f, indent=2)
        
        log.info(f"Proof bundle saved to: {output_path}")
        log.info(f"Proof digest: {bundle['proof_digest'][:32]}...")
        
        return output_path


# ============================================================================
# Main Entry Point
# ============================================================================

def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        description="RIP-302 Proof Collection"
    )
    parser.add_argument(
        "--evidence-dir", "-d",
        type=Path,
        default=None,
        help="Directory containing result files (default: bounties/issue-684/evidence/)"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Output path for proof bundle"
    )
    parser.add_argument(
        "--include-metadata", "-m",
        action="store_true",
        help="Include environment metadata in proof"
    )
    parser.add_argument(
        "--result-files", "-f",
        nargs="+",
        type=Path,
        help="Specific result files to include"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args(argv)
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Determine evidence directory
    evidence_dir = args.evidence_dir
    if evidence_dir is None:
        # Default to evidence directory relative to script
        evidence_dir = Path(__file__).resolve().parent.parent / "evidence"
    
    if not evidence_dir.exists():
        log.error(f"Evidence directory not found: {evidence_dir}")
        return 1
    
    # Collect proof
    collector = ProofCollector(evidence_dir)
    
    # Load results
    result_files = args.result_files
    count = collector.load_results(result_files)
    
    if count == 0:
        log.error("No result files found to collect")
        return 1
    
    log.info(f"Collected {count} result(s)")
    
    # Save proof bundle
    collector.save_proof(args.output, include_metadata=args.include_metadata)
    
    # Print summary
    print("\n" + "=" * 60)
    print("PROOF COLLECTION SUMMARY")
    print("=" * 60)
    print(f"Results collected: {count}")
    print(f"Output file: {args.output}")
    print(f"Proof digest: {collector.compute_proof_digest()[:64]}")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
