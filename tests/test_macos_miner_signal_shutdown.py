from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAC_MINERS = [
    ROOT / "miners" / "macos" / "rustchain_mac_miner_v2.5.py",
    ROOT / "miners" / "macos" / "rustchain_mac_miner_v2.4.py",
    ROOT / "miners" / "macos" / "intel" / "rustchain_mac_miner_v2.4.py",
]


def test_macos_miners_register_sigterm_shutdown_handler():
    for miner_path in MAC_MINERS:
        source = miner_path.read_text(encoding="utf-8")

        assert "import signal" in source
        assert "self.shutdown_requested = False" in source
        assert "def request_shutdown(self, signum=None, frame=None):" in source
        assert "while not self.shutdown_requested:" in source
        assert "signal.signal(signal.SIGTERM, miner.request_shutdown)" in source
        assert "signal.signal(signal.SIGINT, miner.request_shutdown)" in source
