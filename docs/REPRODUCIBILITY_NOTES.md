# Reproducibility Notes — Bounty #1494

Environment setup, validation steps, and reproducibility checklist for the RustChain First API Calls walkthrough and Signed Transfer example.

---

## Environment

### Tested On

| Component | Version |
|-----------|---------|
| Python | 3.12.12 |
| OS | macOS 14.x / Ubuntu 22.04 |
| RustChain Node | 2.2.1-rip200 |

### Dependencies

```bash
# Core dependencies
pip install requests cryptography

# Optional (for mnemonic support)
pip install mnemonic

# For testing
pip install pytest
```

### Requirements File

Create `requirements_bounty1494.txt`:

```txt
requests>=2.28.0
cryptography>=38.0.0
mnemonic>=0.20  # Optional, for BIP39 support
```

Install:

```bash
pip install -r requirements_bounty1494.txt
```

---

## Validation Steps

### Step 1: Verify Node Connectivity

```bash
# Health check
curl -sk https://rustchain.org/health | python3 -m json.tool

# Expected: {"ok": true, "version": "2.2.1-rip200", ...}
```

**Pass Criteria:**
- Response contains `"ok": true`
- Version is `2.2.1-rip200` or later
- Response time < 5 seconds

### Step 2: Verify Epoch Endpoint

```bash
curl -sk https://rustchain.org/epoch | python3 -m json.tool

# Expected: {"epoch": N, "slot": N, "enrolled_miners": N, ...}
```

**Pass Criteria:**
- Response contains `epoch`, `slot`, `enrolled_miners` fields
- All values are non-negative integers

### Step 3: Verify Miners Endpoint

```bash
curl -sk https://rustchain.org/api/miners | python3 -m json.tool

# Expected: Array of miner objects
```

**Pass Criteria:**
- Response is a JSON array
- Each miner has `miner`, `hardware_type`, `antiquity_multiplier` fields

### Step 4: Verify Balance Endpoint

```bash
# Test with known wallet (replace with actual wallet)
curl -sk "https://rustchain.org/wallet/balance?miner_id=scott" | python3 -m json.tool

# Expected: {"ok": true, "miner_id": "scott", "amount_rtc": N, ...}
```

**Pass Criteria:**
- Response contains `ok`, `miner_id`, `amount_rtc` fields
- For non-existent wallets, returns 404 or `ok: false`

### Step 5: Verify Signed Transfer Example (Dry Run)

```bash
# Activate virtual environment (Python 3.12)
source .venv312/bin/activate

# Run dry-run test
python3 examples/signed_transfer_example.py \
    --generate \
    --to RTC0000000000000000000000000000000000000000 \
    --amount 0.001 \
    --dry-run
```

**Pass Criteria:**
- Script generates valid Ed25519 keypair
- Public key is 64 hex characters
- Address is 43 characters (RTC + 40 hex)
- Signature is 128 hex characters
- Output contains "DRY RUN" message
- No exceptions raised

---

## Python 3.12 Verification

### Verify Python Version

```bash
python3 --version
# Expected: Python 3.12.x
```

### Verify Dependencies

```bash
python3 -c "import requests; import cryptography; print('OK')"
# Expected: OK
```

### Run Example Script

```bash
python3 examples/signed_transfer_example.py --help
# Expected: Help message with all options
```

### Test Dry Run

```bash
python3 examples/signed_transfer_example.py \
    --generate \
    --to RTC0000000000000000000000000000000000000000 \
    --amount 0.001 \
    --dry-run 2>&1 | grep "DRY RUN"
# Expected: "🔍 DRY RUN - Transaction NOT submitted"
```

---

## Reproducibility Checklist

### Environment Setup

- [ ] Python 3.12.x installed
- [ ] Virtual environment created
- [ ] Dependencies installed (`requests`, `cryptography`, `mnemonic`)
- [ ] Network access to `https://rustchain.org`

### API Tests

- [ ] Health check returns `ok: true`
- [ ] Epoch endpoint returns valid data
- [ ] Miners endpoint returns array
- [ ] Hall of Fame endpoint returns dict
- [ ] Fee Pool endpoint returns dict
- [ ] Balance endpoint works for known wallet

### Signed Transfer Tests

- [ ] Wallet generation works
- [ ] Address format is correct (RTC + 40 hex)
- [ ] Public key is 64 hex chars
- [ ] Signature is 128 hex chars
- [ ] Dry run completes without errors
- [ ] Signature verification passes (if submitting)

### Documentation

- [ ] `docs/FIRST_API_CALLS.md` is complete
- [ ] `docs/SIGNED_TRANSFER_EXAMPLE.md` is complete
- [ ] `docs/REPRODUCIBILITY_NOTES.md` is complete
- [ ] `examples/signed_transfer_example.py` is executable
- [ ] `requirements_bounty1494.txt` lists all dependencies
- [ ] `validate_bounty1494.sh` runs all tests

---

## Troubleshooting

### Issue: SSL Certificate Error

```
ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Solution:** The node uses a self-signed certificate. Use:
- `curl -k` for curl commands
- `verify=False` for Python requests

### Issue: Module Not Found

```
ModuleNotFoundError: No module named 'cryptography'
```

**Solution:** Install dependencies:
```bash
pip install -r requirements_bounty1494.txt
```

### Issue: Invalid Mnemonic

```
ValueError: Invalid BIP39 mnemonic
```

**Solution:** Ensure mnemonic is 12, 15, 18, 21, or 24 words from the BIP39 wordlist.

### Issue: Connection Timeout

```
requests.exceptions.ConnectionError: Max retries exceeded
```

**Solution:** 
1. Check network connectivity
2. Verify node URL is correct
3. Try alternative node if available

### Issue: Dry Run Failure

If the dry run fails, check:
1. Python version is 3.8+
2. All dependencies are installed
3. Node is accessible (run health check first)
4. Recipient address format is valid (RTC + 40 hex)

---

## Automated Validation

Run the full validation script:

```bash
bash validate_bounty1494.sh
```

Expected output:
```
==============================================
  Bounty #1494 Validation Suite
  Node: https://rustchain.org
==============================================

=== API Endpoint Tests ===
Testing: Health Check... ✓ PASS
Testing: Epoch Info... ✓ PASS
Testing: Miner List... ✓ PASS
Testing: Hall of Fame... ✓ PASS
Testing: Fee Pool... ✓ PASS
Testing: Balance Query... ✓ PASS

=== Python Example Tests ===
Testing: Signed Transfer (dry-run)... ✓ PASS

==============================================
  Results: 7 passed, 0 failed
==============================================
```

---

## Notes for Maintainers

### Node Version Compatibility

This walkthrough was tested against node version `2.2.1-rip200`. If the node API changes:

1. Update version requirements in documentation
2. Verify all endpoints still work as expected
3. Update response examples if schema changes

### Python Version Support

The example script supports Python 3.8+. Key compatibility notes:

- Uses f-strings (Python 3.6+)
- Uses type hints (Python 3.5+)
- Uses `urllib3.disable_warnings` (available in all versions)

### Security Considerations

- Private keys are never logged or transmitted
- Mnemonic phrases are only displayed once during generation
- Dry run mode prevents accidental transactions
- SSL verification is disabled by default (self-signed cert)

---

*Last Updated: March 2026 | Bounty #1494*
