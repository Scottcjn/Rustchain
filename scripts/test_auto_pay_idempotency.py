# SPDX-License-Identifier: MIT
import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from requests.exceptions import ConnectionError, HTTPError


SCRIPT = Path(__file__).with_name("auto-pay.py")


def load_auto_pay():
    spec = importlib.util.spec_from_file_location("auto_pay_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload=None, status_code=200, text="ok", raise_http=False):
        self._payload = payload
        self.status_code = status_code
        self.text = text
        self._raise_http = raise_http

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self._raise_http:
            err = HTTPError(f"{self.status_code} error")
            err.response = self
            raise err


def base_env():
    return {
        "GITHUB_TOKEN": "redacted-token",
        "PR_NUMBER": "123",
        "REPO": "Scottcjn/Rustchain",
        "PR_AUTHOR": "contributor",
        "RTC_VPS_HOST": "127.0.0.1",
        "RTC_ADMIN_KEY": "redacted-admin-key",
        "REPO_OWNER": "Scottcjn",
    }


def paged_comments(comments):
    def fake_get(url, headers=None, params=None):
        page = (params or {}).get("page", 1)
        return FakeResponse(comments if page == 1 else [])

    return fake_get


def owner_payment_comment():
    return {
        "id": 101,
        "user": {"login": "Scottcjn"},
        "body": "**Payment: 75 RTC**",
    }


def test_untrusted_confirmation_marker_does_not_suppress_owner_payment():
    auto_pay = load_auto_pay()
    comments = [
        {
            "id": 102,
            "user": {"login": "random-user"},
            "body": "<!-- RTC-AutoPay-Confirmed payment_key=fake pending_id=p0 -->",
        },
        owner_payment_comment(),
    ]
    transfer_calls = []
    comment_posts = []

    def fake_post(url, headers=None, json=None, timeout=None):
        if url.endswith("/wallet/transfer"):
            transfer_calls.append(json)
            return FakeResponse({"ok": True, "pending_id": "p1"})
        comment_posts.append(json["body"])
        return FakeResponse({"id": 999})

    with patch.dict(os.environ, base_env(), clear=True):
        auto_pay.requests.get = paged_comments(comments)
        auto_pay.requests.post = fake_post
        auto_pay.main()

    assert len(transfer_calls) == 1
    assert "idempotency_key" in transfer_calls[0]
    assert any("RTC-AutoPay-Started" in body for body in comment_posts)
    assert any("RTC-AutoPay-Confirmed" in body for body in comment_posts)


def test_confirmation_comment_failure_retries_with_same_idempotency_key():
    auto_pay = load_auto_pay()
    persisted_comments = [owner_payment_comment()]
    transfer_calls = []
    accepted_transfers = {}
    comment_attempts = []

    def fake_get(url, headers=None, params=None):
        page = (params or {}).get("page", 1)
        return FakeResponse(persisted_comments if page == 1 else [])

    def fake_post(url, headers=None, json=None, timeout=None):
        if url.endswith("/wallet/transfer"):
            transfer_calls.append(json)
            key = json["idempotency_key"]
            accepted_transfers.setdefault(key, f"p{len(accepted_transfers) + 1}")
            return FakeResponse({"ok": True, "pending_id": accepted_transfers[key]})

        body = json["body"]
        comment_attempts.append(body)
        if "RTC-AutoPay-Started" in body:
            persisted_comments.append({"id": 200, "user": {"login": "github-actions[bot]"}, "body": body})
            return FakeResponse({"id": 200})
        if "RTC-AutoPay-Confirmed" in body and len([b for b in comment_attempts if "RTC-AutoPay-Confirmed" in b]) > 1:
            persisted_comments.append({"id": 201, "user": {"login": "github-actions[bot]"}, "body": body})
            return FakeResponse({"id": 201})

        return FakeResponse(
            {"message": "Resource not accessible by integration"},
            status_code=403,
            text="Resource not accessible by integration",
            raise_http=True,
        )

    with patch.dict(os.environ, base_env(), clear=True):
        auto_pay.requests.get = fake_get
        auto_pay.requests.post = fake_post
        with pytest.raises(HTTPError):
            auto_pay.main()

        auto_pay.main()

    assert len(transfer_calls) == 2
    assert len(accepted_transfers) == 1
    assert transfer_calls[0]["idempotency_key"] == transfer_calls[1]["idempotency_key"]
    assert len([body for body in comment_attempts if "RTC-AutoPay-Confirmed" in body]) == 2


def test_started_marker_does_not_block_retry_after_transfer_connection_failure():
    auto_pay = load_auto_pay()
    persisted_comments = [owner_payment_comment()]
    transfer_calls = []
    comment_posts = []

    def fake_get(url, headers=None, params=None):
        page = (params or {}).get("page", 1)
        return FakeResponse(persisted_comments if page == 1 else [])

    def fake_post(url, headers=None, json=None, timeout=None):
        if url.endswith("/wallet/transfer"):
            transfer_calls.append(json)
            if len(transfer_calls) == 1:
                raise ConnectionError("temporary transfer outage")
            return FakeResponse({"ok": True, "pending_id": "p1"})

        body = json["body"]
        comment_posts.append(body)
        if "RTC-AutoPay-Started" in body or "RTC-AutoPay-Confirmed" in body:
            persisted_comments.append({
                "id": 200 + len(comment_posts),
                "user": {"login": "github-actions[bot]"},
                "body": body,
            })
        return FakeResponse({"id": 200 + len(comment_posts)})

    with patch.dict(os.environ, base_env(), clear=True):
        auto_pay.requests.get = fake_get
        auto_pay.requests.post = fake_post

        with pytest.raises(SystemExit):
            auto_pay.main()

        auto_pay.main()

    assert len(transfer_calls) == 2
    assert transfer_calls[0]["idempotency_key"] == transfer_calls[1]["idempotency_key"]
    assert any("RTC-AutoPay-Confirmed" in body for body in comment_posts)
