# SPDX-License-Identifier: MIT
import json
import subprocess
import sys
from pathlib import Path

MINER_PATH = Path(__file__).resolve().parent.parent / "miners" / "openbsd" / "rustchain_openbsd_miner.py"

def test_openbsd_miner_verify_before_trust_flags():
    """Verify that --show-payload, --test-only, and --dry-run execute cleanly and output expected keys."""
    # 1. Test --show-payload
    res = subprocess.run([sys.executable, str(MINER_PATH), "--show-payload"], capture_output=True, text=True)
    assert res.returncode == 0
    payload = json.loads(res.stdout)
    assert "miner_id" in payload
    assert "device_info" in payload
    assert "fingerprint" in payload
    assert payload["signals"]["verify_mode"] == "honest"
    assert "os" in payload["device_info"]

    # 2. Test --test-only
    res_test = subprocess.run([sys.executable, str(MINER_PATH), "--test-only"], capture_output=True, text=True)
    assert res_test.returncode == 0
    assert "[VERIFY-BEFORE-TRUST]" in res_test.stdout
    assert "Clock Drift CV" in res_test.stdout

    # 3. Test --dry-run
    res_dry = subprocess.run([sys.executable, str(MINER_PATH), "--dry-run"], capture_output=True, text=True)
    assert res_dry.returncode == 0
    assert "[DRY-RUN]" in res_dry.stdout
    assert "No packets transmitted" in res_dry.stdout

def test_openbsd_rc_script_exists_and_valid():
    """Ensure rc.d script exists and follows OpenBSD conventions."""
    rc_path = Path(__file__).resolve().parent.parent / "miners" / "openbsd" / "rc.d" / "rustchain_miner"
    assert rc_path.exists()
    content = rc_path.read_text()
    assert ". /etc/rc.d/rc.subr" in content
    assert "rc_cmd $1" in content
