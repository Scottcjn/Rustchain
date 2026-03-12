# RustChain Database Backup Verification - Issue #755

> Automated backup verification tooling for RustChain SQLite database backups with integrity checks, clear exit codes, and CI/CD integration.

## 📋 Overview

This tool provides automated verification of RustChain database backups to ensure backup integrity and recoverability. It performs:

- **SHA-256 Hash Verification** - Validates backup integrity against stored checksums
- **SQLite Readability Checks** - Ensures database can be opened and queried
- **Optional Restore Verification** - Tests backup restoration to temporary location
- **Batch Processing** - Verify multiple backups in a directory
- **Clear Exit Codes** - Designed for CI/CD pipeline integration

## 🚀 Quick Start

### Basic Usage

```bash
# Verify a single backup file
python scripts/verify_backup.py /path/to/backup.db

# Verify with all checks including restore test
python scripts/verify_backup.py /path/to/backup.db --restore

# Verify all backups in a directory
python scripts/verify_backup.py --batch /backups/ --pattern "*.db"

# Output as JSON for CI/CD
python scripts/verify_backup.py backup.db --format json
```

### Installation

No installation required. The tool uses Python 3 standard library only.

```bash
# Clone or navigate to the issue directory
cd bounties/issue-755

# Make script executable (optional)
chmod +x scripts/verify_backup.py
```

## 🔧 Features

### Hash Verification

Automatically verifies SHA-256 checksums when a `.sha256` sidecar file exists:

```bash
# Create hash sidecar file
sha256sum backup.db > backup.db.sha256

# Verify (automatically loads from sidecar)
python scripts/verify_backup.py backup.db

# Or specify hash directly
python scripts/verify_backup.py backup.db --expected-hash "abc123..."
```

### SQLite Integrity Checks

Performs comprehensive database validation:

- `PRAGMA integrity_check` - Full integrity verification
- `PRAGMA quick_check` - Faster structural check
- Table enumeration and row counts
- SQLite format validation

### Restore Verification

Tests backup restoration capability:

```bash
# Copy backup to temp location and verify
python scripts/verify_backup.py backup.db --restore
```

### Batch Processing

Verify multiple backups at once:

```bash
# All .db files in directory
python scripts/verify_backup.py --batch /backups/

# Specific pattern
python scripts/verify_backup.py --batch /backups/ --pattern "rustchain_*.db"
```

## 📊 Exit Codes

| Code | Meaning | Use Case |
|------|---------|----------|
| 0 | All verifications passed | Success in CI/CD |
| 1 | Backup file not found | Missing backup alert |
| 2 | Hash mismatch | Corruption detected |
| 3 | Readability check failed | Database corruption |
| 4 | Restore verification failed | Restore test failed |
| 5 | Invalid backup format | Wrong file type |
| 6 | Batch: partial failure | Some backups invalid |

### CI/CD Example

```yaml
# GitHub Actions example
- name: Verify Database Backups
  run: |
    python scripts/verify_backup.py --batch /backups/ --format json --output results.json
    
- name: Alert on Backup Failure
  if: failure()
  run: |
    echo "Backup verification failed! Check /backups/"
```

## 📁 Directory Structure

```
bounties/issue-755/
├── scripts/
│   └── verify_backup.py      # Main verification tool
├── tests/
│   └── test_verify_backup.py # Comprehensive test suite
├── docs/
│   └── USAGE.md              # Detailed usage guide
├── evidence/
│   └── .gitkeep              # Test evidence directory
├── README.md                 # This file
└── .gitignore
```

## 🧪 Testing

### Run Test Suite

```bash
cd bounties/issue-755
python tests/test_verify_backup.py -v
```

### Test Coverage

- Hash verification (match, mismatch, sidecar loading)
- SQLite readability (valid, corrupted, empty, missing)
- Restore verification
- Batch processing
- Exit codes
- Result serialization

## 📝 Output Formats

### Text Output (Default)

```
[✓ VALID] /backups/rustchain_2026-03-12.db
  Tables: 4, Rows: 15234
  Hash: abc123...

[✗ INVALID] /backups/corrupted.db
  ERROR: Hash mismatch: expected abc..., got def...
  ERROR: Integrity check failed
```

### JSON Output

```json
{
  "results": [
    {
      "backup_path": "/backups/rustchain_2026-03-12.db",
      "timestamp": "2026-03-12T10:30:00Z",
      "hash_check": {
        "passed": true,
        "expected": "abc123...",
        "computed": "abc123..."
      },
      "readability_check": {
        "passed": true,
        "table_count": 4,
        "tables": ["blocks", "transactions", ...],
        "row_counts": {"blocks": 1000, ...}
      },
      "restore_check": {
        "passed": true
      },
      "errors": [],
      "warnings": []
    }
  ],
  "count": 1
}
```

## 🔧 Integration Examples

### Cron Backup Verification

```bash
#!/bin/bash
# /etc/cron.daily/verify-rustchain-backups

BACKUP_DIR="/var/backups/rustchain"
LOG_FILE="/var/log/rustchain/backup-verify.log"

python /opt/rustchain/bounties/issue-755/scripts/verify_backup.py \
    --batch "$BACKUP_DIR" \
    --pattern "*.db" \
    --restore \
    --format json \
    --output "$LOG_FILE"

if [ $? -ne 0 ]; then
    echo "Backup verification failed!" | mail -s "RustChain Backup Alert" admin@example.com
fi
```

### Docker Health Check

```dockerfile
HEALTHCHECK --interval=1h --timeout=5m --start-period=5m --retries=3 \
    CMD python /opt/rustchain/scripts/verify_backup.py \
        /data/rustchain.db --no-hash --quiet || exit 1
```

### Python Integration

```python
from scripts.verify_backup import verify_backup, verify_batch

# Single backup verification
result = verify_backup("/backups/rustchain.db", check_restore=True)
if result.is_valid:
    print(f"Backup valid: {result.table_count} tables")
else:
    print(f"Backup invalid: {result.errors}")

# Batch verification
results, exit_code = verify_batch("/backups/")
```

## 🛠️ Command Reference

### Full Options

```
usage: verify_backup.py [-h] [--batch DIR] [--pattern PATTERN] [--hash]
                        [--no-hash] [--expected-hash HASH] [--readability]
                        [--no-readability] [--restore] [--format {text,json}]
                        [--quiet] [--output FILE]
                        [backup_path]

RustChain Database Backup Verification Tool

positional arguments:
  backup_path          Path to backup file (required unless --batch)

optional arguments:
  -h, --help           show this help message and exit
  --batch DIR          Verify all backups in directory
  --pattern PATTERN    Glob pattern for batch mode (default: *.db)
  --hash               Verify SHA-256 hash (default: enabled)
  --no-hash            Skip hash verification
  --expected-hash HASH
                       Expected SHA-256 hash (overrides sidecar file)
  --readability        Check SQLite readability (default: enabled)
  --no-readability     Skip readability check
  --restore            Perform restore verification
  --format {text,json} Output format (default: text)
  --quiet              Suppress output, only set exit code
  --output FILE        Write results to file (for JSON format)
```

## 📋 Best Practices

### Creating Verified Backups

```bash
# 1. Create backup
cp /var/lib/rustchain/rustchain.db /backups/rustchain_$(date +%Y-%m-%d).db

# 2. Generate hash
sha256sum /backups/rustchain_$(date +%Y-%m-%d).db > /backups/rustchain_$(date +%Y-%m-%d).db.sha256

# 3. Verify immediately
python scripts/verify_backup.py /backups/rustchain_$(date +%Y-%m-%d).db --restore
```

### Automated Verification Schedule

| Frequency | Check Type | Command |
|-----------|-----------|---------|
| After each backup | Hash + Readability | `--no-restore` |
| Daily | Full verification | `--restore` |
| Weekly | Batch all backups | `--batch /backups/` |

## 🔍 Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "Hash mismatch" | Backup may be corrupted; restore from previous valid backup |
| "Not a valid SQLite database" | File may be incomplete or wrong format |
| "Backup file not found" | Check path and file permissions |
| Restore test fails | Ensure sufficient temp disk space |

### Debug Mode

```bash
# Get detailed JSON output for debugging
python scripts/verify_backup.py backup.db --format json | jq .
```

## 📄 License

MIT License - See [LICENSE](../../../LICENSE) for details.

## 🙏 Acknowledgments

- RustChain Community ([rustchain.org](https://rustchain.org))
- SQLite Documentation
- Python Standard Library

---

**Issue**: #755
**Status**: Implemented
**Version**: 1.0.0
**Created**: 2026-03-12
