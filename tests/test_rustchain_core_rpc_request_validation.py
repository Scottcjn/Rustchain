# SPDX-License-Identifier: MIT
"""Regression tests for RustChain core RPC request shape validation."""

import importlib.util
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RPC_PATH = PROJECT_ROOT / "rips" / "rustchain-core" / "api" / "rpc.py"


def load_rpc_module():
    spec = importlib.util.spec_from_file_location("rustchain_core_rpc", RPC_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def rpc_handler():
    rpc = load_rpc_module()
    handler = object.__new__(rpc.ApiRequestHandler)
    handler.api = rpc.RustChainApi(rpc.MockNode())
    return rpc, handler


@pytest.mark.parametrize("payload", [[], "not-an-object", 1, None])
def test_route_request_rejects_non_object_post_bodies(rpc_handler, payload):
    rpc, handler = rpc_handler

    response = handler._route_request("/rpc", payload)

    assert response.success is False
    assert response.error == rpc.JSON_BODY_OBJECT_ERROR


@pytest.mark.parametrize("params", [[], "not-an-object", 1, None])
def test_rpc_endpoint_rejects_non_object_params(rpc_handler, params):
    rpc, handler = rpc_handler

    response = handler._route_request(
        "/rpc",
        {"method": "getWallet", "params": params},
    )

    assert response.success is False
    assert response.error == rpc.RPC_PARAMS_OBJECT_ERROR


def test_rpc_endpoint_accepts_object_params(rpc_handler):
    _rpc, handler = rpc_handler

    response = handler._route_request(
        "/rpc",
        {"method": "getWallet", "params": {"address": "RTC1Test"}},
    )

    assert response.success is True
    assert response.data["address"] == "RTC1Test"
