from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
MAC_MINERS = [
    ROOT / "miners" / "macos" / "rustchain_mac_miner_v2.5.py",
    ROOT / "miners" / "macos" / "rustchain_mac_miner_v2.4.py",
    ROOT / "miners" / "macos" / "intel" / "rustchain_mac_miner_v2.4.py",
]


def load_miner_module(miner_path):
    module_name = "mac_miner_{}".format(abs(hash(miner_path)))
    spec = importlib.util.spec_from_file_location(module_name, miner_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_macos_miners_register_sigterm_shutdown_handler():
    for miner_path in MAC_MINERS:
        source = miner_path.read_text(encoding="utf-8")

        assert "import signal" in source
        assert "self.shutdown_requested = False" in source
        assert "def request_shutdown(self, signum=None, frame=None):" in source
        assert "while not self.shutdown_requested:" in source
        assert "signal.signal(signal.SIGTERM, miner.request_shutdown)" in source
        assert "signal.signal(signal.SIGINT, miner.request_shutdown)" in source
        assert "def sleep_until_shutdown(self, seconds, interval=1.0):" in source
        assert "self.sleep_until_shutdown(30)" in source
        assert "self.sleep_until_shutdown(LOTTERY_CHECK_INTERVAL)" in source


def test_shutdown_sleep_helper_returns_after_shutdown_request(monkeypatch):
    for miner_path in MAC_MINERS:
        module = load_miner_module(miner_path)
        miner = module.MacMiner.__new__(module.MacMiner)
        miner.shutdown_requested = False
        sleeps = []

        def fake_sleep(seconds):
            sleeps.append(seconds)
            miner.shutdown_requested = True

        monkeypatch.setattr(module.time, "sleep", fake_sleep)

        miner.sleep_until_shutdown(30)

        assert sleeps, "expected {} to sleep in short checkpoints".format(miner_path)
        assert max(sleeps) <= 1.0
        assert miner.shutdown_requested
