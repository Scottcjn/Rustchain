# SPDX-License-Identifier: MIT

import re

import bcos_directory


def test_bcos_directory_secret_key_uses_environment(monkeypatch):
    monkeypatch.setenv('BCOS_DIRECTORY_SECRET_KEY', 'configured-secret')

    assert bcos_directory.load_secret_key() == 'configured-secret'


def test_bcos_directory_secret_key_fallback_is_not_public_constant(monkeypatch):
    monkeypatch.delenv('BCOS_DIRECTORY_SECRET_KEY', raising=False)

    secret = bcos_directory.load_secret_key()

    assert secret != 'bcos-directory-dev-key'
    assert re.fullmatch(r'[0-9a-f]{64}', secret)


def test_bcos_directory_debug_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv('BCOS_DIRECTORY_DEBUG', raising=False)
    assert bcos_directory.debug_enabled() is False

    monkeypatch.setenv('BCOS_DIRECTORY_DEBUG', 'true')
    assert bcos_directory.debug_enabled() is True


def test_bcos_directory_host_defaults_to_loopback(monkeypatch):
    monkeypatch.delenv('BCOS_DIRECTORY_HOST', raising=False)

    assert bcos_directory.server_host() == '127.0.0.1'
