# SPDX-License-Identifier: MIT

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "rips" / "rustchain-core" / "api" / "rpc.py"


def _load_rpc_module():
    spec = importlib.util.spec_from_file_location("rustchain_core_rpc_allowlist_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rpc_endpoint_rejects_state_changing_methods():
    rpc = _load_rpc_module()
    api = rpc.RustChainApi(rpc.MockNode())
    handler = object.__new__(rpc.ApiRequestHandler)
    handler.api = api

    response = handler._route_request(
        "/rpc",
        {
            "method": "createProposal",
            "params": {
                "title": "malicious",
                "description": "should not be created",
                "proposer": "attacker",
            },
        },
    )

    assert response.success is False
    assert response.error == "Method not allowed: createProposal"


def test_rpc_endpoint_allows_read_only_methods():
    rpc = _load_rpc_module()
    api = rpc.RustChainApi(rpc.MockNode())
    handler = object.__new__(rpc.ApiRequestHandler)
    handler.api = api

    response = handler._route_request("/rpc", {"method": "getStats", "params": {}})

    assert response.success is True
    assert response.data["chain_id"] == 2718
