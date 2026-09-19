import urllib.request
import requests
import pytest
from miners.linux.fingerprint_checks import check_anti_emulation, validate_all_checks
from miners.linux.rustchain_linux_miner import LocalMiner, main

def test_check_anti_emulation_respects_skip_network_probes(monkeypatch):
    """Verify that skip_network_probes=True prevents any outbound requests to link-local cloud metadata endpoints."""
    network_calls = []

    def mock_urlopen(req, *args, **kwargs):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        network_calls.append(url)
        raise RuntimeError(f"Network probe attempted to: {url}")

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    # When skip_network_probes is False, urllib.request.urlopen is invoked
    check_anti_emulation(skip_network_probes=False)
    assert len(network_calls) > 0, "Expected network probes when skip_network_probes is False"

    network_calls.clear()

    # When skip_network_probes is True, zero network probes are attempted
    valid, data = check_anti_emulation(skip_network_probes=True)
    assert len(network_calls) == 0, f"Expected 0 network calls with skip_network_probes=True, got: {network_calls}"
    assert "vm_indicators" in data

def test_validate_all_checks_passes_skip_network_probes(monkeypatch):
    """Verify validate_all_checks with skip_network_probes=True executes without touching urllib."""
    network_calls = []

    def mock_urlopen(req, *args, **kwargs):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        network_calls.append(url)
        raise RuntimeError(f"Network probe attempted to: {url}")

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    passed, results = validate_all_checks(include_rom_check=False, skip_network_probes=True)
    assert len(network_calls) == 0
    assert "anti_emulation" in results

def test_miner_offline_dry_run_makes_zero_network_calls(monkeypatch):
    """Verify LocalMiner with offline=True executes dry_run() with zero HTTP requests across urllib and requests."""
    outbound_attempts = []

    def mock_urlopen(req, *args, **kwargs):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        outbound_attempts.append(("urllib", url))
        raise RuntimeError(f"Outbound urllib attempt blocked: {url}")

    def mock_requests_get(url, *args, **kwargs):
        outbound_attempts.append(("requests", str(url)))
        raise RuntimeError(f"Outbound requests.get attempt blocked: {url}")

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    monkeypatch.setattr(requests, "get", mock_requests_get)

    miner = LocalMiner(
        wallet="RTCtestwallet123",
        persist_key=False,
        offline=True,
        verbose=True,
    )
    result = miner.dry_run()

    assert result is True
    assert len(outbound_attempts) == 0, f"Expected zero outbound attempts in offline dry-run, got: {outbound_attempts}"

def test_miner_main_cli_offline_flag(monkeypatch):
    """Verify CLI accepts --dry-run and --offline flags without error or network calls."""
    outbound_attempts = []

    def mock_urlopen(req, *args, **kwargs):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        outbound_attempts.append(("urllib", url))
        raise RuntimeError("Blocked")

    def mock_requests_get(url, *args, **kwargs):
        outbound_attempts.append(("requests", str(url)))
        raise RuntimeError("Blocked")

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    monkeypatch.setattr(requests, "get", mock_requests_get)

    code = main(["--dry-run", "--offline", "--wallet", "RTCclitestwallet"])
    assert code == 0
    assert len(outbound_attempts) == 0

def test_offline_flags_rejected_in_real_mining():
    """Verify LocalMiner and CLI strictly reject --offline or --skip-network-probes when not in --dry-run mode."""
    with pytest.raises(ValueError, match="Security violation.*permitted ONLY with --dry-run"):
        LocalMiner(wallet="RTCtestwallet123", persist_key=True, offline=True)

    with pytest.raises(ValueError, match="Security violation.*permitted ONLY with --dry-run"):
        LocalMiner(wallet="RTCtestwallet123", persist_key=True, skip_network_probes=True)

    # CLI level rejection
    with pytest.raises(SystemExit):
        main(["--offline", "--wallet", "RTCclitestwallet"])

    with pytest.raises(SystemExit):
        main(["--skip-network-probes", "--wallet", "RTCclitestwallet"])

def test_real_mining_mode_runs_metadata_probes(monkeypatch):
    """Verify that in normal mining mode, check_anti_emulation always queries the link-local metadata endpoint."""
    probed_urls = []

    def mock_urlopen(req, *args, **kwargs):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        probed_urls.append(url)
        raise urllib.error.URLError("Connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    # Real mining calls validate_all_checks without skip_network_probes
    validate_all_checks(include_rom_check=False, skip_network_probes=False)
    assert any("169.254.169.254" in u for u in probed_urls), "Expected cloud metadata endpoint probe in real mining"

