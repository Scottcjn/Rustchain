# SPDX-License-Identifier: MIT

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import server_proxy


class DummyResponse:
    def __init__(self, text, status_code=200, content_type="text/plain"):
        self.text = text
        self.status_code = status_code
        self.headers = {"Content-Type": content_type} if content_type is not None else {}

    def json(self):
        raise ValueError("not json")


class JsonResponse(DummyResponse):
    def __init__(self, payload, status_code=200):
        super().__init__("", status_code, "application/json")
        self.payload = payload

    def json(self):
        return self.payload


def test_proxy_preserves_non_json_upstream_response(monkeypatch):
    upstream = DummyResponse("<h1>upstream failed</h1>", status_code=502, content_type="text/html")
    monkeypatch.setattr(server_proxy.requests, "get", lambda *args, **kwargs: upstream)

    server_proxy.app.config["TESTING"] = True
    response = server_proxy.app.test_client().get("/api/stats")

    assert response.status_code == 502
    assert response.get_data(as_text=True) == "<h1>upstream failed</h1>"
    assert response.content_type == "text/html"


def test_proxy_json_response_still_uses_json_body(monkeypatch):
    upstream = JsonResponse({"ok": True}, status_code=201)
    monkeypatch.setattr(server_proxy.requests, "get", lambda *args, **kwargs: upstream)

    server_proxy.app.config["TESTING"] = True
    response = server_proxy.app.test_client().get("/api/stats")

    assert response.status_code == 201
    assert response.get_json() == {"ok": True}


def test_proxy_request_exception_does_not_leak_internal_details(monkeypatch):
    def fail(*args, **kwargs):
        raise server_proxy.requests.exceptions.ConnectionError("secret upstream path")

    monkeypatch.setattr(server_proxy.requests, "get", fail)

    server_proxy.app.config["TESTING"] = True
    response = server_proxy.app.test_client().get("/api/stats")

    assert response.status_code == 502
    assert response.get_json() == {"error": "Local server request failed"}
    assert "secret upstream path" not in response.get_data(as_text=True)
