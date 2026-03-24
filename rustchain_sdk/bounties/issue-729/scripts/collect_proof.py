#!/usr/bin/env python3
"""
Collect proof bundle for bounty #729 submission.
Gathers test results, manifest info, and evidence into a single proof.json file.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

def collect_git_info() -> Dict[str, Any]:
    """Collect git repository information."""
    import subprocess
    
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H|%ai|%s"],
            capture_output=True, text=True, cwd=Path(__file__).parent.parent
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split("|")
            return {
                "commit_hash": parts[0],
                "commit_date": parts[1],
                "commit_message": parts[2]
            }
    except Exception:
        pass
    
    return {"error": "Could not retrieve git info"}

def collect_system_info() -> Dict[str, Any]:
    """Collect system/environment information."""
    import platform
    
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

def collect_manifest_info() -> Dict[str, Any]:
    """Collect extension manifest information."""
    manifest_path = Path(__file__).parent.parent / "extension" / "manifest.json"
    
    if not manifest_path.exists():
        return {"error": "manifest.json not found"}
    
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    return {
        "name": manifest.get("name"),
        "version": manifest.get("version"),
        "description": manifest.get("description"),
        "manifest_version": manifest.get("manifest_version"),
        "permissions": manifest.get("permissions", []),
        "host_permissions": manifest.get("host_permissions", [])
    }

def collect_test_results() -> List[Dict[str, Any]]:
    """Collect test results from evidence directory."""
    evidence_dir = Path(__file__).parent.parent / "evidence"
    results: List[Dict[str, Any]] = []
    
    if not evidence_dir.exists():
        return results
    
    for evidence_file in evidence_dir.glob("test_*.json"):
        try:
            with open(evidence_file) as f:
                result = json.load(f)
            results.append(result)
        except Exception as e:
            results.append({
                "file": evidence_file.name,
                "error": str(e)
            })
    
    return results

def collect_file_inventory() -> Dict[str, Any]:
    """Collect inventory of extension files."""
    extension_dir = Path(__file__).parent.parent / "extension"
    inventory = {
        "total_files": 0,
        "by_type": {},
        "files": []
    }
    
    if not extension_dir.exists():
        return inventory
    
    for file_path in extension_dir.rglob("*"):
        if file_path.is_file():
            rel_path = str(file_path.relative_to(extension_dir))
            ext = file_path.suffix or "no_extension"
            
            inventory["total_files"] += 1
            inventory["by_type"][ext] = inventory["by_type"].get(ext, 0) + 1
            inventory["files"].append({
                "path": rel_path,
                "size_bytes": file_path.stat().st_size,
                "extension": ext
            })
    
    return inventory

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Collect proof bundle for bounty submission")
    parser.add_argument("--output", "-o", default="proof.json", help="Output file path")
    parser.add_argument("--include-metadata", action="store_true", help="Include system metadata")
    args = parser.parse_args()
    
    print("Collecting proof bundle for bounty #729...")
    
    proof = {
        "bounty_id": "issue-729",
        "bounty_title": "BoTTube Chrome Extension",
        "submission_type": "Chrome Extension MVP",
        "entry_points": ["browse", "vote", "upload"],
        "collected_at": datetime.utcnow().isoformat() + "Z",
        
        "manifest": collect_manifest_info(),
        "test_results": collect_test_results(),
        "file_inventory": collect_file_inventory(),
    }
    
    if args.include_metadata:
        print("Including system metadata...")
        proof["git_info"] = collect_git_info()
        proof["system_info"] = collect_system_info()
    
    # Calculate summary
    test_results = proof.get("test_results", [])
    passed = sum(1 for r in test_results if r.get("status") == "passed")
    total = len(test_results)
    
    proof["summary"] = {
        "tests_passed": passed,
        "tests_total": total,
        "test_pass_rate": f"{passed/total*100:.1f}%" if total > 0 else "N/A",
        "total_files": proof["file_inventory"].get("total_files", 0),
        "ready_for_submission": passed == total and total > 0
    }
    
    # Write output
    output_path = Path(args.output)
    with open(output_path, 'w') as f:
        json.dump(proof, f, indent=2)
    
    print(f"\nProof bundle collected: {output_path}")
    print(f"\nSummary:")
    print(f"  Tests: {passed}/{total} passed")
    print(f"  Files: {proof['file_inventory'].get('total_files', 0)} extension files")
    print(f"  Ready for submission: {proof['summary']['ready_for_submission']}")
    
    return 0 if proof['summary']['ready_for_submission'] else 1

if __name__ == "__main__":
    sys.exit(main())
