#!/usr/bin/env python3
"""
Vintage Hardware Submission Validator
======================================

Validates bounty #2314 submissions for completeness and correctness.

Usage:
    python3 validate_vintage_submission.py \
        --photo evidence/photo.jpg \
        --screenshot evidence/screenshot.png \
        --attestation-log evidence/attestation.log \
        --writeup evidence/writeup.md \
        --wallet RTC1VintageWallet123456789
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional


HAVE_PILLOW: bool = False
try:
    from PIL import Image  # type: ignore
    HAVE_PILLOW = True
except ImportError:
    Image = None  # type: ignore


class SubmissionValidator:
    """Validates vintage hardware bounty submissions"""
    
    def __init__(self):
        self.checks: Dict[str, Dict[str, Any]] = {}
        self.errors: list = []
        self.warnings: list = []
    
    def _validate_image_core(self, file_path: str, label: str,
                             min_size: int = 10000,
                             min_resolution: tuple = (640, 480)) -> Dict[str, Any]:
        """Real image content validation using Pillow.

        Args:
            file_path: Path to the image file.
            label: 'Photo' or 'Screenshot' for error messages.
            min_size: Minimum file size in bytes.
            min_resolution: Minimum (width, height) in pixels.

        Returns:
            Dict with status (PASS/FAIL/WARN), message, and checks dict.
        """
        result = {"status": "FAIL", "message": "", "checks": {}}

        if not os.path.exists(file_path):
            result["message"] = f"{label} file not found: {file_path}"
            return result

        file_size = os.path.getsize(file_path)
        result["checks"]["file_exists"] = True
        result["checks"]["file_size_bytes"] = file_size

        if file_size < min_size:
            result["status"] = "WARN"
            result["message"] = f"{label} file seems too small: {file_size} bytes"
            self.warnings.append(f"{label} file is unusually small")
            # Still try to validate — let Pillow judge content

        # Verify with Pillow that it's a real image
        if not HAVE_PILLOW:
            result["status"] = "FAIL"
            result["message"] = f"{label} image validation requires Pillow (pip install Pillow)"
            result["checks"]["pillow_available"] = False
            return result

        try:
            img = Image.open(file_path)
            img.verify()  # Checks image header integrity (fast, no pixel decode)
            # Re-open to get dimensions (verify() invalidates the file handle)
            img = Image.open(file_path)
            width, height = img.size
            result["checks"]["width"] = width
            result["checks"]["height"] = height
            result["checks"]["format"] = img.format

            # Check resolution
            if width < min_resolution[0] or height < min_resolution[1]:
                result["status"] = "WARN"
                msg = f"{label} resolution {width}x{height} is below {min_resolution[0]}x{min_resolution[1]}"
                result["message"] = (result["message"] + "; " + msg) if result["message"] else msg
                self.warnings.append(f"{label} resolution too low")

            # Check extension matches format
            ext = os.path.splitext(file_path)[1].lower().lstrip(".")
            if img.format and ext and ext not in img.format.lower() and ext not in ("jpg", "jpeg"):
                # jpg/jpeg are interchangeable
                if not (ext in ("jpg", "jpeg") and img.format.lower() in ("jpeg", "jpg")):
                    result["status"] = "WARN"
                    msg = f"{label} extension .{ext} doesn't match format {img.format}"
                    result["message"] = (result["message"] + "; " + msg) if result["message"] else msg
                    self.warnings.append(f"{label} extension/format mismatch")

            # If we got here with no warnings, PASS
            if result["status"] not in ("WARN",):
                result["status"] = "PASS"
                result["message"] = f"{label} validated as real image ({width}x{height}, {img.format})"

        except Exception as e:
            # PIL couldn't identify the file — don't overwrite existing size/format warnings
            if result["status"] != "WARN":
                result["status"] = "FAIL"
                result["message"] = f"{label} is not a valid image: {e}"
                result["checks"]["validation_error"] = str(e)
            else:
                # Add format warning about unrecognized image extension
                ext = os.path.splitext(file_path)[1].lower()
                known_img_exts = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".svg")
                if ext and ext not in known_img_exts:
                    msg = f"Unusual photo format: {ext}"
                    result["message"] = (result["message"] + "; " + msg) if result["message"] else msg
                result["checks"]["format"] = ext if ext else "unknown"

        return result

    def validate_photo(self, photo_path: str) -> Dict[str, Any]:
        """Validate photo evidence with real image content check"""
        return self._validate_image_core(photo_path, "Photo",
                                         min_size=10000,
                                         min_resolution=(640, 480))

    def validate_screenshot(self, screenshot_path: str) -> Dict[str, Any]:
        """Validate screenshot with real image content check"""
        return self._validate_image_core(screenshot_path, "Screenshot",
                                         min_size=1000,
                                         min_resolution=(320, 240))
    
    def validate_attestation_log(self, log_path: str) -> Dict[str, Any]:
        """Validate server-side attestation log"""
        result = {
            "status": "FAIL",
            "message": "",
            "checks": {}
        }
        
        if not os.path.exists(log_path):
            result["message"] = f"Attestation log not found: {log_path}"
            return result
        
        try:
            with open(log_path, 'r') as f:
                content = f.read()
            
            # Try to parse as JSON
            try:
                log_data = json.loads(content)
                result["checks"]["json_valid"] = True
                if not isinstance(log_data, dict):
                    result["message"] = "Attestation log JSON root must be an object"
                    result["status"] = "FAIL"
                    return result
                
                # Check required fields
                required_fields = [
                    "miner_id",
                    "device_arch",
                    "fingerprint_hash",
                    "timestamp"
                ]
                
                missing_fields = []
                for field in required_fields:
                    if field not in log_data:
                        missing_fields.append(field)
                
                if missing_fields:
                    result["message"] = f"Missing fields: {missing_fields}"
                    result["status"] = "FAIL"
                else:
                    result["status"] = "PASS"
                    result["message"] = "Attestation log is valid JSON with required fields"
                    result["checks"]["miner_id"] = log_data.get("miner_id")
                    result["checks"]["device_arch"] = log_data.get("device_arch")
                    result["checks"]["has_fingerprint"] = "fingerprint_hash" in log_data
                    result["checks"]["has_timestamp"] = "timestamp" in log_data
                
            except json.JSONDecodeError as e:
                # Not JSON, check for plain text format
                if "miner_id" in content or "device_arch" in content:
                    result["status"] = "PASS"
                    result["message"] = "Attestation log appears valid (plain text format)"
                    result["checks"]["format"] = "plain_text"
                else:
                    result["status"] = "WARN"
                    result["message"] = f"Log is not valid JSON: {e}"
                    result["checks"]["format"] = "unknown"
        
        except Exception as e:
            result["message"] = f"Error reading log: {e}"
        
        return result
    
    def validate_writeup(self, writeup_path: str) -> Dict[str, Any]:
        """Validate machine write-up"""
        result = {
            "status": "FAIL",
            "message": "",
            "checks": {}
        }
        
        if not os.path.exists(writeup_path):
            result["message"] = f"Writeup not found: {writeup_path}"
            return result
        
        try:
            with open(writeup_path, 'r') as f:
                content = f.read()
            
            # Check for required sections
            required_keywords = [
                ("CPU", "cpu"),
                ("OS", "os"),
                ("memory", "ram"),
                ("storage", "storage"),
            ]
            
            found_sections = []
            missing_sections = []
            
            for section_name, keyword in required_keywords:
                if keyword.lower() in content.lower():
                    found_sections.append(section_name)
                else:
                    missing_sections.append(section_name)
            
            result["checks"]["found_sections"] = found_sections
            result["checks"]["missing_sections"] = missing_sections
            
            if missing_sections:
                result["status"] = "WARN"
                result["message"] = f"Missing sections: {missing_sections}"
                self.warnings.append(f"Writeup missing: {missing_sections}")
            else:
                result["status"] = "PASS"
                result["message"] = "Writeup contains all required sections"
            
            # Check word count
            word_count = len(content.split())
            result["checks"]["word_count"] = word_count
            
            if word_count < 100:
                result["status"] = "WARN"
                result["message"] = f"Writeup seems too short ({word_count} words)"
                self.warnings.append(f"Writeup is only {word_count} words")
        
        except Exception as e:
            result["message"] = f"Error reading writeup: {e}"
        
        return result
    
    def validate_wallet(self, wallet_address: str) -> Dict[str, Any]:
        """Validate RTC wallet address format"""
        result = {
            "status": "FAIL",
            "message": "",
            "checks": {}
        }
        
        if not wallet_address:
            result["message"] = "Wallet address not provided"
            return result
        
        # Check format: RTC1 + 40 alphanumeric chars
        if not wallet_address.startswith("RTC1"):
            result["message"] = "Wallet must start with 'RTC1'"
            return result
        
        address_part = wallet_address[4:]
        if len(address_part) < 30 or len(address_part) > 50:
            result["message"] = f"Wallet address length invalid: {len(address_part)} chars"
            return result
        
        # Check alphanumeric
        if not address_part.isalnum():
            result["message"] = "Wallet address must be alphanumeric"
            return result
        
        result["status"] = "PASS"
        result["message"] = "Wallet address format is valid"
        result["checks"] = {
            "prefix": "RTC1",
            "address_length": len(wallet_address),
            "format": "valid"
        }
        
        return result
    
    def calculate_bounty(self, device_arch: str) -> int:
        """Calculate bounty based on architecture era"""
        # Import from hardware_profiles if available
        try:
            sys.path.insert(0, 'vintage_miner')
            from hardware_profiles import get_bounty
            return get_bounty(device_arch)
        except Exception:
            # Default bounty
            return 100
    
    def validate_submission(
        self,
        photo_path: Optional[str] = None,
        screenshot_path: Optional[str] = None,
        attestation_log_path: Optional[str] = None,
        writeup_path: Optional[str] = None,
        wallet_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate complete submission
        
        Returns:
            Dictionary with validation results
        """
        results = {
            "valid": True,
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "errors": [],
            "warnings": [],
            "bounty": None,
            "era": None
        }
        
        # Validate each component
        if photo_path:
            results["checks"]["photo"] = self.validate_photo(photo_path)
            if results["checks"]["photo"]["status"] == "FAIL":
                results["valid"] = False
                results["errors"].append("Photo validation failed")
        
        if screenshot_path:
            results["checks"]["screenshot"] = self.validate_screenshot(screenshot_path)
            if results["checks"]["screenshot"]["status"] == "FAIL":
                results["valid"] = False
                results["errors"].append("Screenshot validation failed")
        
        if attestation_log_path:
            log_result = self.validate_attestation_log(attestation_log_path)
            results["checks"]["attestation_log"] = log_result
            
            if log_result["status"] == "FAIL":
                results["valid"] = False
                results["errors"].append("Attestation log validation failed")
            
            # Extract device_arch for bounty calculation
            if "device_arch" in log_result.get("checks", {}):
                device_arch = log_result["checks"]["device_arch"]
                results["device_arch"] = device_arch
                results["bounty"] = self.calculate_bounty(device_arch)
                
                # Determine era
                try:
                    from hardware_profiles import get_era
                    results["era"] = get_era(device_arch)
                except Exception:
                    results["era"] = "Unknown"
        
        if writeup_path:
            results["checks"]["writeup"] = self.validate_writeup(writeup_path)
            if results["checks"]["writeup"]["status"] == "FAIL":
                results["valid"] = False
                results["errors"].append("Writeup validation failed")
        
        if wallet_address:
            results["checks"]["wallet"] = self.validate_wallet(wallet_address)
            if results["checks"]["wallet"]["status"] == "FAIL":
                results["valid"] = False
                results["errors"].append("Wallet validation failed")
        
        # Add warnings
        results["warnings"] = self.warnings
        
        return results


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Validate Vintage Hardware Bounty Submission (#2314)"
    )
    
    parser.add_argument(
        "--photo", "-p",
        help="Path to photo evidence"
    )
    
    parser.add_argument(
        "--screenshot", "-s",
        help="Path to miner output screenshot"
    )
    
    parser.add_argument(
        "--attestation-log", "-a",
        help="Path to server-side attestation log"
    )
    
    parser.add_argument(
        "--writeup", "-w",
        help="Path to machine writeup"
    )
    
    parser.add_argument(
        "--wallet",
        help="RTC wallet address for bounty payout"
    )
    
    parser.add_argument(
        "--output", "-o",
        help="Output file for validation results (JSON)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    # Check if any input provided
    if not any([args.photo, args.screenshot, args.attestation_log, args.writeup, args.wallet]):
        parser.print_help()
        print("\nError: At least one validation input is required")
        return 1
    
    # Create validator
    validator = SubmissionValidator()
    
    # Run validation
    results = validator.validate_submission(
        photo_path=args.photo,
        screenshot_path=args.screenshot,
        attestation_log_path=args.attestation_log,
        writeup_path=args.writeup,
        wallet_address=args.wallet
    )
    
    # Print results
    print("=" * 80)
    print("VINTAGE HARDWARE SUBMISSION VALIDATION RESULTS")
    print("=" * 80)
    print(f"Timestamp: {results['timestamp']}")
    print(f"Overall Status: {'✅ VALID' if results['valid'] else '❌ INVALID'}")
    print()
    
    # Print individual checks
    for check_name, check_result in results.get("checks", {}).items():
        status = check_result.get("status", "UNKNOWN")
        status_icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "SKIP": "⊘"}.get(status, "?")
        print(f"{status_icon} {check_name}: {check_result.get('message', '')}")
        
        if args.verbose and "checks" in check_result:
            for key, value in check_result["checks"].items():
                print(f"    {key}: {value}")
    
    # Print bounty info
    if results.get("bounty"):
        print()
        print(f"💰 Estimated Bounty: {results['bounty']} RTC")
        print(f"📅 Era: {results.get('era', 'Unknown')}")
        print(f"🖥️ Device Arch: {results.get('device_arch', 'Unknown')}")
    
    # Print errors
    if results.get("errors"):
        print()
        print("❌ Errors:")
        for error in results["errors"]:
            print(f"  - {error}")
    
    # Print warnings
    if results.get("warnings"):
        print()
        print("⚠️ Warnings:")
        for warning in results["warnings"]:
            print(f"  - {warning}")
    
    # Save to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Results saved to: {args.output}")
    
    print("=" * 80)
    
    return 0 if results["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
