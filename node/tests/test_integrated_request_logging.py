# SPDX-License-Identifier: MIT

import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "rustchain_v2_integrated_v2.2.1_rip200.py"


def load_integrated_module():
    spec = importlib.util.spec_from_file_location("rustchain_integrated_request_logging_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_after_request_emits_structured_request_log(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin-key-for-request-logging")
    module = load_integrated_module()
    info = Mock()
    monkeypatch.setattr(module.app.logger, "info", info)

    response = module.app.test_client().get("/definitely-missing", headers={"X-Request-Id": "req-test-1"})

    assert response.status_code == 404
    assert response.headers["X-Request-Id"] == "req-test-1"
    info.assert_called()
    payload = json.loads(info.call_args.args[0])
    assert payload["req_id"] == "req-test-1"
    assert payload["method"] == "GET"
    assert payload["path"] == "/definitely-missing"
    assert payload["status"] == 404


def _loggers(monkeypatch, module):
    info, debug = Mock(), Mock()
    monkeypatch.setattr(module.app.logger, "info", info)
    monkeypatch.setattr(module.app.logger, "debug", debug)
    return info, debug


def test_successful_requests_log_at_debug_not_info(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin-key-for-request-logging")
    monkeypatch.delenv("RC_LOG_ALL_REQUESTS", raising=False)
    module = load_integrated_module()
    info, debug = _loggers(monkeypatch, module)

    response = module.app.test_client().get("/health", headers={"X-Request-Id": "req-ok"})

    assert response.status_code < 400
    assert response.headers["X-Request-Id"] == "req-ok"
    assert not any('"req_id":"req-ok"' in str(c.args[0]) for c in info.call_args_list)
    lines = [json.loads(c.args[0]) for c in debug.call_args_list if '"req_id":"req-ok"' in str(c.args[0])]
    assert lines and lines[-1]["lvl"] == "DEBUG" and lines[-1]["path"] == "/health"


def test_log_all_requests_env_restores_info(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin-key-for-request-logging")
    monkeypatch.setenv("RC_LOG_ALL_REQUESTS", "1")
    module = load_integrated_module()
    info, debug = _loggers(monkeypatch, module)

    module.app.test_client().get("/health", headers={"X-Request-Id": "req-all"})

    lines = [json.loads(c.args[0]) for c in info.call_args_list if '"req_id":"req-all"' in str(c.args[0])]
    assert lines and lines[-1]["lvl"] == "INFO"
