#!/usr/bin/env python3
"""
RustChain Database Backup Verification Tool

Automated verification of RustChain SQLite database backups with:
- SHA-256 hash integrity checks
- File readability validation
- Optional restore verification
- Clear exit codes for CI/CD integration

Usage:
    python verify_backup.py <backup_file> [options]
    python verify_backup.py --batch <backup_dir> [options]
"""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# Exit codes
EXIT_SUCCESS = 0
EXIT_FILE_NOT_FOUND = 1
EXIT_HASH_MISMATCH = 2
EXIT_READABILITY_FAILED = 3
EXIT_RESTORE_FAILED = 4
EXIT_INVALID_BACKUP = 5
EXIT_BATCH_PARTIAL_FAILURE = 6


class BackupVerificationResult:
    """Represents the result of a backup verification."""

    def __init__(self, backup_path: str):
        self.backup_path = backup_path
        self.timestamp = datetime.utcnow().isoformat() + "Z"
        self.hash_check_passed: bool = False
        self.readability_check_passed: bool = False
        self.restore_check_passed: Optional[bool] = None
        self.expected_hash: Optional[str] = None
        self.computed_hash: Optional[str] = None
        self.table_count: Optional[int] = None
        self.tables: List[str] = []
        self.row_counts: Dict[str, int] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def to_dict(self) -> Dict:
        return {
            "backup_path": self.backup_path,
            "timestamp": self.timestamp,
            "hash_check": {
                "passed": self.hash_check_passed,
                "expected": self.expected_hash,
                "computed": self.computed_hash,
            },
            "readability_check": {
                "passed": self.readability_check_passed,
                "table_count": self.table_count,
                "tables": self.tables,
                "row_counts": self.row_counts,
            },
            "restore_check": {
                "passed": self.restore_check_passed,
            },
            "errors": self.errors,
            "warnings": self.warnings,
        }

    @property
    def is_valid(self) -> bool:
        return self.hash_check_passed and self.readability_check_passed


def compute_sha256(filepath: str) -> Optional[str]:
    """Compute SHA-256 hash of a file."""
    if not os.path.exists(filepath):
        return None

    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except IOError as e:
        raise IOError(f"Failed to read file for hashing: {e}")


def load_expected_hash(backup_path: str) -> Optional[str]:
    """Load expected hash from .sha256 sidecar file."""
    hash_file = f"{backup_path}.sha256"
    if not os.path.exists(hash_file):
        return None

    try:
        with open(hash_file, "r") as f:
            content = f.read().strip()
            # Handle both formats: "hash  filename" and just "hash"
            parts = content.split()
            if len(parts) >= 1:
                return parts[0].lower()
    except IOError:
        pass
    return None


def check_sqlite_integrity(db_path: str) -> Tuple[bool, List[str], List[str]]:
    """
    Check SQLite database integrity using PRAGMA commands.

    Returns:
        Tuple of (passed, errors, warnings)
    """
    errors = []
    warnings = []

    # Check file exists
    if not os.path.exists(db_path):
        errors.append(f"File does not exist: {db_path}")
        return False, errors, warnings

    # Check file is not empty
    if os.path.getsize(db_path) == 0:
        errors.append("File is empty")
        return False, errors, warnings

    try:
        # Use URI mode to open read-only and avoid creating new database
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Quick check - verify it's a valid SQLite database
        try:
            cursor.execute("SELECT sqlite_version();")
            cursor.fetchone()
        except sqlite3.DatabaseError as e:
            errors.append(f"Not a valid SQLite database: {e}")
            conn.close()
            return False, errors, warnings

        # Integrity check
        cursor.execute("PRAGMA integrity_check;")
        integrity_result = cursor.fetchone()[0]
        if integrity_result != "ok":
            errors.append(f"Integrity check failed: {integrity_result}")

        # Quick check
        cursor.execute("PRAGMA quick_check;")
        quick_result = cursor.fetchone()[0]
        if quick_result != "ok":
            warnings.append(f"Quick check warning: {quick_result}")

        # Get table list
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
        tables = [row[0] for row in cursor.fetchall()]

        # Get row counts for each table
        row_counts = {}
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM \"{table}\";")
                row_counts[table] = cursor.fetchone()[0]
            except sqlite3.Error as e:
                warnings.append(f"Could not count rows in {table}: {e}")
                row_counts[table] = -1

        conn.close()

        passed = len(errors) == 0
        return passed, errors, warnings

    except sqlite3.Error as e:
        errors.append(f"Database connection error: {e}")
        return False, errors, warnings


def verify_restore(backup_path: str, temp_dir: Optional[str] = None) -> Tuple[bool, str]:
    """
    Verify backup can be restored by copying to temp location and checking.

    Returns:
        Tuple of (success, error_message)
    """
    cleanup_temp = temp_dir is None

    if temp_dir is None:
        temp_dir = tempfile.mkdtemp(prefix="rustchain_backup_verify_")

    try:
        # Create restore path
        backup_name = os.path.basename(backup_path)
        restore_path = os.path.join(temp_dir, backup_name)

        # Copy backup to temp location (simulating restore)
        shutil.copy2(backup_path, restore_path)

        # Verify the restored copy
        passed, errors, warnings = check_sqlite_integrity(restore_path)

        if not passed:
            return False, f"Restored backup failed integrity check: {'; '.join(errors)}"

        # Clean up restored file
        os.remove(restore_path)

        return True, ""

    except shutil.Error as e:
        return False, f"Failed to copy backup for restore test: {e}"
    except IOError as e:
        return False, f"IO error during restore test: {e}"
    finally:
        if cleanup_temp and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


def verify_backup(
    backup_path: str,
    check_hash: bool = True,
    check_readability: bool = True,
    check_restore: bool = False,
    expected_hash: Optional[str] = None,
) -> BackupVerificationResult:
    """
    Perform comprehensive backup verification.

    Args:
        backup_path: Path to the backup file
        check_hash: Whether to verify SHA-256 hash
        check_readability: Whether to check SQLite readability
        check_restore: Whether to perform restore verification
        expected_hash: Optional expected hash (overrides sidecar file)

    Returns:
        BackupVerificationResult with all check results
    """
    result = BackupVerificationResult(backup_path)

    # Check file exists
    if not os.path.exists(backup_path):
        result.errors.append(f"Backup file not found: {backup_path}")
        return result

    # Check file is not empty
    if os.path.getsize(backup_path) == 0:
        result.errors.append("Backup file is empty")
        return result

    # Hash check
    if check_hash:
        try:
            result.computed_hash = compute_sha256(backup_path)

            # Use provided hash or load from sidecar
            if expected_hash:
                result.expected_hash = expected_hash.lower()
            else:
                result.expected_hash = load_expected_hash(backup_path)

            if result.expected_hash:
                result.hash_check_passed = result.computed_hash == result.expected_hash
                if not result.hash_check_passed:
                    result.errors.append(
                        f"Hash mismatch: expected {result.expected_hash}, "
                        f"got {result.computed_hash}"
                    )
            else:
                # No expected hash available - just record computed hash
                result.hash_check_passed = True
                result.warnings.append("No expected hash found, skipping hash verification")
        except IOError as e:
            result.errors.append(f"Hash computation failed: {e}")
    else:
        # Hash check skipped - mark as passed
        result.hash_check_passed = True

    # Readability check
    if check_readability:
        try:
            passed, errors, warnings = check_sqlite_integrity(backup_path)
            result.readability_check_passed = passed
            result.errors.extend(errors)
            result.warnings.extend(warnings)

            if passed:
                # Extract table info on success
                conn = sqlite3.connect(backup_path)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
                )
                result.tables = [row[0] for row in cursor.fetchall()]
                result.table_count = len(result.tables)

                for table in result.tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM \"{table}\";")
                        result.row_counts[table] = cursor.fetchone()[0]
                    except sqlite3.Error:
                        result.row_counts[table] = -1

                conn.close()
        except Exception as e:
            result.readability_check_passed = False
            result.errors.append(f"Readability check failed: {e}")

    # Restore check (optional)
    if check_restore and result.is_valid:
        try:
            success, error_msg = verify_restore(backup_path)
            result.restore_check_passed = success
            if not success:
                result.errors.append(f"Restore verification failed: {error_msg}")
        except Exception as e:
            result.restore_check_passed = False
            result.errors.append(f"Restore verification error: {e}")

    return result


def verify_batch(
    backup_dir: str,
    pattern: str = "*.db",
    check_hash: bool = True,
    check_readability: bool = True,
    check_restore: bool = False,
) -> Tuple[List[BackupVerificationResult], int]:
    """
    Verify all backup files in a directory.

    Returns:
        Tuple of (results list, exit code)
    """
    import glob

    backup_pattern = os.path.join(backup_dir, pattern)
    backup_files = sorted(glob.glob(backup_pattern))

    if not backup_files:
        print(f"No backup files found matching: {backup_pattern}", file=sys.stderr)
        return [], EXIT_FILE_NOT_FOUND

    results = []
    failures = 0

    for backup_path in backup_files:
        print(f"\nVerifying: {backup_path}")
        result = verify_backup(
            backup_path,
            check_hash=check_hash,
            check_readability=check_readability,
            check_restore=check_restore,
        )
        results.append(result)

        if result.is_valid:
            print(f"  ✓ Valid backup")
        else:
            print(f"  ✗ Invalid backup: {'; '.join(result.errors)}")
            failures += 1

    # Determine exit code
    if failures == 0:
        return results, EXIT_SUCCESS
    elif failures == len(results):
        return results, EXIT_INVALID_BACKUP
    else:
        return results, EXIT_BATCH_PARTIAL_FAILURE


def format_output(
    results: List[BackupVerificationResult], output_format: str
) -> str:
    """Format verification results for output."""
    if output_format == "json":
        return json.dumps(
            {"results": [r.to_dict() for r in results], "count": len(results)},
            indent=2,
        )
    elif output_format == "text":
        lines = []
        for r in results:
            status = "✓ VALID" if r.is_valid else "✗ INVALID"
            lines.append(f"[{status}] {r.backup_path}")
            if r.errors:
                for err in r.errors:
                    lines.append(f"  ERROR: {err}")
            if r.warnings:
                for warn in r.warnings:
                    lines.append(f"  WARNING: {warn}")
            if r.table_count is not None:
                lines.append(f"  Tables: {r.table_count}, Rows: {sum(r.row_counts.values())}")
        return "\n".join(lines)
    else:
        raise ValueError(f"Unknown output format: {output_format}")


def main():
    parser = argparse.ArgumentParser(
        description="RustChain Database Backup Verification Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Codes:
  0  - All verifications passed
  1  - Backup file not found
  2  - Hash mismatch
  3  - Readability check failed
  4  - Restore verification failed
  5  - Invalid backup format
  6  - Batch: partial failure (some backups invalid)

Examples:
  # Verify single backup with hash and readability checks
  python verify_backup.py /backups/rustchain_2026-03-12.db

  # Verify with restore test
  python verify_backup.py /backups/rustchain.db --restore

  # Verify all backups in directory
  python verify_backup.py --batch /backups/ --pattern "*.db"

  # Output as JSON for CI/CD
  python verify_backup.py backup.db --format json
        """,
    )

    parser.add_argument(
        "backup_path",
        nargs="?",
        help="Path to backup file (required unless --batch)",
    )
    parser.add_argument(
        "--batch",
        metavar="DIR",
        help="Verify all backups in directory",
    )
    parser.add_argument(
        "--pattern",
        default="*.db",
        help="Glob pattern for batch mode (default: *.db)",
    )
    parser.add_argument(
        "--hash",
        dest="check_hash",
        action="store_true",
        default=True,
        help="Verify SHA-256 hash (default: enabled)",
    )
    parser.add_argument(
        "--no-hash",
        dest="check_hash",
        action="store_false",
        help="Skip hash verification",
    )
    parser.add_argument(
        "--expected-hash",
        metavar="HASH",
        help="Expected SHA-256 hash (overrides sidecar file)",
    )
    parser.add_argument(
        "--readability",
        dest="check_readability",
        action="store_true",
        default=True,
        help="Check SQLite readability (default: enabled)",
    )
    parser.add_argument(
        "--no-readability",
        dest="check_readability",
        action="store_false",
        help="Skip readability check",
    )
    parser.add_argument(
        "--restore",
        dest="check_restore",
        action="store_true",
        help="Perform restore verification (copies to temp location)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output, only set exit code",
    )
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="Write results to file (for JSON format)",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.backup_path and not args.batch:
        parser.error("Either backup_path or --batch is required")

    if args.backup_path and args.batch:
        parser.error("Cannot specify both backup_path and --batch")

    # Run verification
    if args.batch:
        results, exit_code = verify_batch(
            args.batch,
            pattern=args.pattern,
            check_hash=args.check_hash,
            check_readability=args.check_readability,
            check_restore=args.check_restore,
        )
    else:
        result = verify_backup(
            args.backup_path,
            check_hash=args.check_hash,
            check_readability=args.check_readability,
            check_restore=args.check_restore,
            expected_hash=args.expected_hash,
        )
        results = [result]

        if not result.is_valid:
            if result.errors and "not found" in result.errors[0].lower():
                exit_code = EXIT_FILE_NOT_FOUND
            elif not result.hash_check_passed:
                exit_code = EXIT_HASH_MISMATCH
            elif not result.readability_check_passed:
                exit_code = EXIT_READABILITY_FAILED
            else:
                exit_code = EXIT_INVALID_BACKUP
        else:
            exit_code = EXIT_SUCCESS

    # Output results
    if not args.quiet and results:
        output = format_output(results, args.format)
        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
        else:
            print(output)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
