#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import importlib.util
import sys
import types
from pathlib import Path


def load_verifier_module():
    module_path = Path(__file__).resolve().parents[1] / "verifier.py"

    github_module = types.ModuleType("github")

    class StubGithub:
        def __init__(self, token):
            self.token = token

    class StubGithubException(Exception):
        pass

    github_module.Github = StubGithub
    github_module.GithubException = StubGithubException

    google_module = types.ModuleType("google")
    google_module.__path__ = []
    generativeai_module = types.ModuleType("google.generativeai")
    generativeai_module.configure = lambda **kwargs: None
    generativeai_module.GenerativeModel = lambda name: object()
    google_module.generativeai = generativeai_module

    dotenv_module = types.ModuleType("dotenv")
    dotenv_module.load_dotenv = lambda: None

    stubs = {
        "github": github_module,
        "google": google_module,
        "google.generativeai": generativeai_module,
        "dotenv": dotenv_module,
    }
    originals = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)

    try:
        spec = importlib.util.spec_from_file_location(
            "bounty_bot_pro_verifier_test_subject", module_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, original in originals.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


verifier = load_verifier_module()


def test_verify_stars_error_keeps_report_shape():
    class FailingGitHub:
        def get_user(self, username):
            raise verifier.GithubException("rate limit")

    subject = verifier.BountyVerifier.__new__(verifier.BountyVerifier)
    subject.gh = FailingGitHub()

    result = subject.verify_stars("alice")

    assert result["count"] == 0
    assert result["is_star_king"] is False
    assert result["repos"] == []
    assert "rate limit" in result["error"]


def test_generate_report_uses_verified_reward_inputs_without_network():
    subject = verifier.BountyVerifier.__new__(verifier.BountyVerifier)
    subject.verify_stars = lambda username: {
        "count": 2,
        "is_star_king": True,
        "repos": ["Scottcjn/Rustchain", "Scottcjn/bottube"],
    }
    subject.verify_following = lambda username: True
    subject.verify_wallet = lambda wallet: {"exists": True, "balance": 12.5}

    report = subject.generate_report("alice", "alice-wallet")

    assert "@alice" in report
    assert "alice-wallet" in report
    assert "12.5 RTC" in report
    assert "**28.0 RTC**" in report
