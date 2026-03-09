#!/usr/bin/env python3
"""
BoTTube Chrome Extension Test Suite
Tests extension functionality, API integration, and manifest validity.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional, Dict, List
from datetime import datetime

# Test results storage
EVIDENCE_DIR = Path(__file__).parent.parent / "evidence"
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

class TestResult:
    """Store test result for evidence collection."""
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.timestamp = datetime.utcnow().isoformat() + "Z"
        self.status = "pending"
        self.details: Dict[str, Any] = {}
        self.error: Optional[str] = None
    
    def pass_(self, details: Optional[Dict[str, Any]] = None):
        self.status = "passed"
        if details:
            self.details = details
    
    def fail(self, error: str):
        self.status = "failed"
        self.error = error
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "test_name": self.test_name,
            "timestamp": self.timestamp,
            "status": self.status,
            "details": self.details,
            "error": self.error
        }

def save_evidence(result: TestResult):
    """Save test result to evidence directory."""
    EVIDENCE_DIR.mkdir(exist_ok=True)
    output_file = EVIDENCE_DIR / f"test_{result.test_name.replace(' ', '_')}.json"
    with open(output_file, 'w') as f:
        json.dump(result.to_dict(), f, indent=2)
    print(f"  Evidence saved: {output_file}")

def test_manifest_validity() -> TestResult:
    """Test that manifest.json is valid and complete."""
    result = TestResult("manifest_validity")
    
    try:
        manifest_path = Path(__file__).parent.parent / "extension" / "manifest.json"
        if not manifest_path.exists():
            result.fail("manifest.json not found")
            return result
        
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        # Required fields
        required_fields = [
            "manifest_version", "name", "version", "description",
            "action", "background", "permissions"
        ]
        
        missing = [f for f in required_fields if f not in manifest]
        if missing:
            result.fail(f"Missing required fields: {missing}")
            return result
        
        # Validate manifest version
        if manifest["manifest_version"] != 3:
            result.fail(f"Expected manifest_version 3, got {manifest['manifest_version']}")
            return result
        
        # Validate permissions
        required_perms = ["storage", "tabs"]
        missing_perms = [p for p in required_perms if p not in manifest.get("permissions", [])]
        
        result.pass_({
            "manifest_version": manifest["manifest_version"],
            "name": manifest["name"],
            "version": manifest["version"],
            "permissions": manifest.get("permissions", []),
            "missing_optional_permissions": missing_perms if missing_perms else None
        })
        
    except json.JSONDecodeError as e:
        result.fail(f"Invalid JSON: {e}")
    except Exception as e:
        result.fail(str(e))
    
    return result

def test_file_structure() -> TestResult:
    """Test that all required files exist."""
    result = TestResult("file_structure")
    
    extension_dir = Path(__file__).parent.parent / "extension"
    required_files = [
        "manifest.json",
        "popup/popup.html",
        "popup/popup.css",
        "popup/popup.js",
        "background/service-worker.js",
        "content/youtube-integration.js",
        "content/content-styles.css",
        "options/options.html",
        "options/options.css",
        "options/options.js",
    ]
    
    missing_files = []
    for file_path in required_files:
        full_path = extension_dir / file_path
        if not full_path.exists():
            missing_files.append(file_path)
    
    if missing_files:
        result.fail(f"Missing files: {missing_files}")
    else:
        result.pass_({
            "total_files": len(required_files),
            "all_present": True
        })
    
    return result

def test_popup_html() -> TestResult:
    """Test popup HTML has required entry points."""
    result = TestResult("popup_html")
    
    try:
        popup_path = Path(__file__).parent.parent / "extension" / "popup" / "popup.html"
        with open(popup_path) as f:
            content = f.read()
        
        # Check for entry point buttons
        entry_points = {
            "browse": 'id="btn-browse"',
            "vote": 'id="btn-vote"',
            "upload": 'id="btn-upload"'
        }
        
        missing = []
        for name, selector in entry_points.items():
            if selector not in content:
                missing.append(name)
        
        if missing:
            result.fail(f"Missing entry points: {missing}")
        else:
            result.pass_({
                "entry_points_found": list(entry_points.keys()),
                "html_valid": True
            })
    
    except Exception as e:
        result.fail(str(e))
    
    return result

def test_background_service_worker() -> TestResult:
    """Test background service worker has required handlers."""
    result = TestResult("background_service_worker")
    
    try:
        sw_path = Path(__file__).parent.parent / "extension" / "background" / "service-worker.js"
        with open(sw_path) as f:
            content = f.read()
        
        # Check for required message handlers
        required_handlers = [
            "getBalance",
            "submitVote",
            "uploadVideo",
            "fetchTrending"
        ]
        
        missing = []
        for handler in required_handlers:
            if handler not in content:
                missing.append(handler)
        
        if missing:
            result.fail(f"Missing handlers: {missing}")
        else:
            result.pass_({
                "handlers_found": required_handlers,
                "service_worker_valid": True
            })
    
    except Exception as e:
        result.fail(str(e))
    
    return result

def test_content_script() -> TestResult:
    """Test content script has YouTube integration."""
    result = TestResult("content_script")
    
    try:
        cs_path = Path(__file__).parent.parent / "extension" / "content" / "youtube-integration.js"
        with open(cs_path) as f:
            content = f.read()
        
        # Check for YouTube-specific integration
        youtube_features = [
            "ytd-video-owner-renderer",  # YouTube video element selector
            "showVotingUI",
            "showUploadModal",
            "getCurrentVideoInfo"
        ]
        
        missing = []
        for feature in youtube_features:
            if feature not in content:
                missing.append(feature)
        
        if missing:
            result.fail(f"Missing YouTube features: {missing}")
        else:
            result.pass_({
                "youtube_features": youtube_features,
                "content_script_valid": True
            })
    
    except Exception as e:
        result.fail(str(e))
    
    return result

def test_options_page() -> TestResult:
    """Test options page has API configuration."""
    result = TestResult("options_page")
    
    try:
        options_path = Path(__file__).parent.parent / "extension" / "options" / "options.html"
        with open(options_path) as f:
            content = f.read()
        
        # Check for API key input
        required_elements = [
            'id="api-key"',
            'id="btn-test-connection"',
            'id="wallet-address-input"'
        ]
        
        missing = []
        for elem in required_elements:
            if elem not in content:
                missing.append(elem)
        
        if missing:
            result.fail(f"Missing options elements: {missing}")
        else:
            result.pass_({
                "elements_found": required_elements,
                "options_page_valid": True
            })
    
    except Exception as e:
        result.fail(str(e))
    
    return result

def test_api_endpoints_defined() -> TestResult:
    """Test that API endpoints are properly defined."""
    result = TestResult("api_endpoints")
    
    try:
        sw_path = Path(__file__).parent.parent / "extension" / "background" / "service-worker.js"
        with open(sw_path) as f:
            content = f.read()
        
        # Check for API endpoint definitions
        endpoints = [
            "/health",
            "/api/videos",
            "/api/vote",
            "/api/upload"
        ]
        
        missing = []
        for endpoint in endpoints:
            if endpoint not in content:
                missing.append(endpoint)
        
        if missing:
            result.fail(f"Missing endpoint definitions: {missing}")
        else:
            result.pass_({
                "endpoints_defined": endpoints,
                "api_config_valid": True
            })
    
    except Exception as e:
        result.fail(str(e))
    
    return result

def run_all_tests() -> list[TestResult]:
    """Run all tests and return results."""
    tests = [
        test_manifest_validity,
        test_file_structure,
        test_popup_html,
        test_background_service_worker,
        test_content_script,
        test_options_page,
        test_api_endpoints_defined,
    ]
    
    results = []
    print("\n" + "=" * 60)
    print("BoTTube Chrome Extension Test Suite")
    print("=" * 60 + "\n")
    
    for test_func in tests:
        print(f"Running: {test_func.__name__}...")
        result = test_func()
        results.append(result)
        save_evidence(result)
        
        status_icon = "✅" if result.status == "passed" else "❌"
        print(f"  {status_icon} {result.test_name}: {result.status}")
        if result.error:
            print(f"     Error: {result.error}")
        print()
    
    # Summary
    passed = sum(1 for r in results if r.status == "passed")
    total = len(results)
    
    print("=" * 60)
    print(f"SUMMARY: {passed}/{total} tests passed")
    print("=" * 60 + "\n")
    
    return results

def main():
    """Main entry point."""
    results = run_all_tests()
    
    # Exit with error if any tests failed
    failed = sum(1 for r in results if r.status == "failed")
    sys.exit(1 if failed > 0 else 0)

if __name__ == "__main__":
    main()
