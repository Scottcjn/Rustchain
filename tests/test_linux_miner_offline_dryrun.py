# SPDX-License-Identifier: MIT
import subprocess
import sys
import unittest.mock as mock
from pathlib import Path
import importlib.util

REPO_ROOT = Path(__file__).resolve().parents[1]
MINER_PATH = REPO_ROOT / "miners" / "linux" / "rustchain_linux_miner.py"
FINGERPRINT_PATH = REPO_ROOT / "miners" / "linux" / "fingerprint_checks.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_linux_miner_help_documents_offline_and_skip_network_probes():
    result = subprocess.run(
        [sys.executable, str(MINER_PATH), "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    help_text = " ".join(result.stdout.split())
    assert "--offline" in help_text
    assert "--skip-network-probes" in help_text


def test_miner_dry_run_offline_makes_zero_network_calls():
    miner_mod = load_module("rustchain_linux_miner_offline_test", MINER_PATH)
    fp_mod = load_module("fingerprint_checks_offline_test", FINGERPRINT_PATH)

    recorded_calls = []

    def mock_urlopen(req, *args, **kwargs):
        url = getattr(req, "full_url", str(req))
        recorded_calls.append(("urllib", url))
        raise RuntimeError(f"Unexpected network attempt: {url}")

    def mock_get(url, *args, **kwargs):
        recorded_calls.append(("requests.get", url))
        raise RuntimeError(f"Unexpected network attempt: {url}")

    miner = miner_mod.LocalMiner(
        wallet="RTCtestwallet0000000000000000000000000000",
        persist_key=False,
        offline=True,
    )

    with mock.patch("urllib.request.urlopen", side_effect=mock_urlopen), \
         mock.patch("requests.get", side_effect=mock_get):
        res = miner.dry_run()

    assert res is True
    assert len(recorded_calls) == 0, f"Expected 0 network calls, got: {recorded_calls}"


def test_miner_skip_network_probes_anti_emulation():
    fp_mod = load_module("fingerprint_checks_probes_test", FINGERPRINT_PATH)

    recorded_urls = []

    def mock_urlopen(req, *args, **kwargs):
        url = getattr(req, "full_url", str(req))
        recorded_urls.append(url)
        raise RuntimeError(f"Unexpected network call: {url}")

    with mock.patch("urllib.request.urlopen", side_effect=mock_urlopen):
        # When skipping network probes, urlopen should not be invoked at all
        valid, data = fp_mod.check_anti_emulation(skip_network_probes=True)

    assert len(recorded_urls) == 0
    assert "vm_indicators" in data
