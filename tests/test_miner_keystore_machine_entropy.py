# SPDX-License-Identifier: MIT
"""Keystore key derivation must be per-machine and never a public constant.

Regression tests for the Windows keystore bug: with no machine-id branch on
Windows, miner_crypto fell back to sha256("fallback-no-machine-id"), so every
Windows keystore was obscured with the same public key material.
"""
import builtins
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

nacl_signing = pytest.importorskip("nacl.signing")

REPO_ROOT = Path(__file__).resolve().parents[1]
CRYPTO_PATHS = {
    "linux": REPO_ROOT / "miners" / "linux" / "miner_crypto.py",
    "windows": REPO_ROOT / "miners" / "windows" / "miner_crypto.py",
}
LEGACY = hashlib.sha256(b"fallback-no-machine-id").digest()
PASSPHRASE_ENV = "RUSTCHAIN_KEYSTORE_PASSPHRASE"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=sorted(CRYPTO_PATHS))
def crypto(request):
    return _load(CRYPTO_PATHS[request.param], f"miner_crypto_{request.param}_under_test")


def _no_machine_id_files(monkeypatch, module):
    real_open = builtins.open

    def fake_open(path, *args, **kwargs):
        if str(path) in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            raise FileNotFoundError(path)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(module, "open", fake_open, raising=False)


def _fake_winreg(guid):
    mod = types.ModuleType("winreg")
    mod.HKEY_LOCAL_MACHINE = object()
    mod.KEY_READ = 0x20019
    mod.KEY_WOW64_64KEY = 0x0100
    seen = {}

    class _Key:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def open_key(root, sub_key, reserved=0, access=0):
        seen["open"] = (root, sub_key)
        if guid is None:
            raise FileNotFoundError(sub_key)
        return _Key()

    def query_value_ex(key, name):
        seen["value"] = name
        return guid, 1

    mod.OpenKey = open_key
    mod.QueryValueEx = query_value_ex
    mod.seen = seen
    return mod


def _as_windows(monkeypatch, module, guid):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv(PASSPHRASE_ENV, raising=False)
    winreg = _fake_winreg(guid)
    monkeypatch.setitem(sys.modules, "winreg", winreg)
    _no_machine_id_files(monkeypatch, module)
    return winreg


def test_windows_uses_machine_guid(monkeypatch, crypto):
    guid = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
    winreg = _as_windows(monkeypatch, crypto, guid)

    entropy = crypto._get_machine_entropy()

    assert entropy == hashlib.sha256(guid.encode()).digest()
    assert entropy != LEGACY
    assert winreg.seen["open"][1] == r"SOFTWARE\Microsoft\Cryptography"
    assert winreg.seen["value"] == "MachineGuid"


def test_different_machine_guids_give_different_keys(monkeypatch, crypto):
    _as_windows(monkeypatch, crypto, "guid-machine-a")
    key_a = crypto._get_machine_entropy()
    _as_windows(monkeypatch, crypto, "guid-machine-b")
    key_b = crypto._get_machine_entropy()

    assert key_a != key_b


def test_no_identifier_raises_instead_of_constant(monkeypatch, crypto, tmp_path):
    _as_windows(monkeypatch, crypto, None)  # MachineGuid missing

    with pytest.raises(RuntimeError, match=PASSPHRASE_ENV):
        crypto._get_machine_entropy()

    kp = {"private_key": "11" * 32, "public_key": "22" * 32}
    with pytest.raises(RuntimeError):
        crypto.save_keystore(kp, str(tmp_path / "miner_key.json"))
    assert not (tmp_path / "miner_key.json").exists()


def test_no_identifier_with_passphrase_uses_passphrase(monkeypatch, crypto):
    _as_windows(monkeypatch, crypto, None)
    monkeypatch.setenv(PASSPHRASE_ENV, "correct horse battery staple")
    key_1 = crypto._get_machine_entropy()
    monkeypatch.setenv(PASSPHRASE_ENV, "another passphrase")
    key_2 = crypto._get_machine_entropy()

    assert len(key_1) == 32
    assert key_1 != LEGACY
    assert key_1 != key_2


def test_linux_machine_id_derivation_unchanged(monkeypatch, crypto):
    """Existing Linux keystores must keep decrypting: key = sha256(machine-id)."""
    monkeypatch.setattr(sys, "platform", "linux")
    real_open = builtins.open

    def fake_open(path, *args, **kwargs):
        if str(path) == "/etc/machine-id":
            import io
            return io.StringIO("abcdef0123456789\n")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(crypto, "open", fake_open, raising=False)

    assert crypto._get_machine_entropy() == hashlib.sha256(b"abcdef0123456789").digest()


def _legacy_keystore(path):
    sk = nacl_signing.SigningKey.generate()
    priv = bytes(sk)
    pub = bytes(sk.verify_key).hex()
    obscured = bytes(a ^ b for a, b in zip(priv, LEGACY))
    path.write_text(json.dumps({
        "version": 1, "public_key": pub, "obscured_private": obscured.hex(),
    }))
    return priv.hex(), pub


def test_legacy_fallback_keystore_loads_and_is_migrated(monkeypatch, crypto, tmp_path, capsys):
    guid = "machine-guid-for-migration"
    _as_windows(monkeypatch, crypto, guid)
    ks = tmp_path / "miner_key.json"
    priv, pub = _legacy_keystore(ks)

    loaded = crypto.get_or_create_keypair(str(ks))

    assert loaded == {"private_key": priv, "public_key": pub}
    assert "WARNING" in capsys.readouterr().out

    stored = json.loads(ks.read_text())
    real = hashlib.sha256(guid.encode()).digest()
    assert stored["public_key"] == pub
    assert bytes.fromhex(stored["obscured_private"]) == bytes(
        a ^ b for a, b in zip(bytes.fromhex(priv), real)
    )
    # No longer recoverable with the public constant.
    assert bytes(a ^ b for a, b in zip(bytes.fromhex(stored["obscured_private"]), LEGACY)).hex() != priv

    # Second load uses the real key directly (no legacy path, no warning).
    assert crypto.load_keystore(str(ks)) == {"private_key": priv, "public_key": pub}
    assert "WARNING" not in capsys.readouterr().out


def test_undecryptable_keystore_is_preserved_not_overwritten(monkeypatch, crypto, tmp_path):
    _as_windows(monkeypatch, crypto, "some-guid")
    ks = tmp_path / "miner_key.json"
    ks.write_text(json.dumps({
        "version": 1, "public_key": "33" * 32, "obscured_private": "44" * 32,
    }))
    original = ks.read_text()

    kp = crypto.get_or_create_keypair(str(ks))

    backups = list(tmp_path.glob("miner_key.json.unreadable-*"))
    assert len(backups) == 1 and backups[0].read_text() == original
    assert json.loads(ks.read_text())["public_key"] == kp["public_key"]


@pytest.mark.parametrize("platform_dir,filename", [
    ("linux", "rustchain_linux_miner.py"),
    ("windows", "rustchain_windows_miner.py"),
])
def test_crypto_available_false_when_nacl_missing(monkeypatch, platform_dir, filename):
    for name in ("nacl", "nacl.signing", "nacl.encoding"):
        monkeypatch.setitem(sys.modules, name, None)  # import -> ImportError
    monkeypatch.delitem(sys.modules, "miner_crypto", raising=False)
    monkeypatch.syspath_prepend(str(REPO_ROOT / "miners" / platform_dir))

    miner = _load(REPO_ROOT / "miners" / platform_dir / filename,
                  f"{platform_dir}_miner_nacl_missing_under_test")

    assert miner.CRYPTO_AVAILABLE is False
    monkeypatch.delitem(sys.modules, "miner_crypto", raising=False)
