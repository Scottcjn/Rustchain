# SPDX-License-Identifier: MIT

from io import BytesIO
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.rpc import ApiRequestHandler, ApiResponse


def _post_response(body, path="/rpc"):
    handler = object.__new__(ApiRequestHandler)
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = BytesIO(body)
    handler.path = path

    responses = []
    routed = []

    def route_request(route_path, params):
        routed.append((route_path, params))
        return ApiResponse(success=True, data={"routed": True})

    handler._route_request = route_request
    handler._send_response = responses.append
    handler.do_POST()
    return responses, routed


def test_post_rejects_malformed_json_without_routing():
    responses, routed = _post_response(b'{"method":')

    assert routed == []
    assert len(responses) == 1
    assert responses[0].success is False
    assert responses[0].error == "Invalid JSON request body"


def test_post_rejects_non_object_json_without_routing():
    responses, routed = _post_response(b'[]')

    assert routed == []
    assert len(responses) == 1
    assert responses[0].success is False
    assert responses[0].error == "JSON request body must be an object"


def test_post_routes_valid_json_object():
    responses, routed = _post_response(
        b'{"method": "getStats", "params": {"limit": 1}}'
    )

    assert routed == [("/rpc", {"method": "getStats", "params": {"limit": 1}})]
    assert len(responses) == 1
    assert responses[0].success is True
