# SPDX-License-Identifier: MIT
import importlib.util
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from requests.exceptions import ConnectionError, HTTPError


SCRIPT = Path(__file__).with_name("auto-pay.py")


def load_auto_pay():
    spec = importlib.util.spec_from_file_location("auto_pay_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.requests.delete = lambda url, headers=None, timeout=None: FakeResponse(status_code=204)
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
        "GITHUB_SHA": "0123456789abcdef0123456789abcdef01234567",
    }


def paged_comments(comments):
    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/repos/Scottcjn/Rustchain"):
            return FakeResponse({"default_branch": "main"})
        if url.endswith("/git/ref/heads/main"):
            return FakeResponse({"object": {"sha": "abcdef0123456789abcdef0123456789abcdef01"}})
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
        assert json is not None
        if url.endswith("/git/refs"):
            return FakeResponse({"ref": json["ref"]}, status_code=201)
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

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/repos/Scottcjn/Rustchain"):
            return FakeResponse({"default_branch": "main"})
        if url.endswith("/git/ref/heads/main"):
            return FakeResponse({"object": {"sha": "abcdef0123456789abcdef0123456789abcdef01"}})
        page = (params or {}).get("page", 1)
        return FakeResponse(persisted_comments if page == 1 else [])

    def fake_post(url, headers=None, json=None, timeout=None):
        assert json is not None
        if url.endswith("/git/refs"):
            return FakeResponse({"ref": json["ref"]}, status_code=201)
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

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/repos/Scottcjn/Rustchain"):
            return FakeResponse({"default_branch": "main"})
        if url.endswith("/git/ref/heads/main"):
            return FakeResponse({"object": {"sha": "abcdef0123456789abcdef0123456789abcdef01"}})
        page = (params or {}).get("page", 1)
        return FakeResponse(persisted_comments if page == 1 else [])

    def fake_post(url, headers=None, json=None, timeout=None):
        assert json is not None
        if url.endswith("/git/refs"):
            return FakeResponse({"ref": json["ref"]}, status_code=201)
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


def test_fresh_started_marker_blocks_concurrent_transfer_attempt():
    auto_pay = load_auto_pay()
    payment = owner_payment_comment()
    payment_key = auto_pay.build_payment_key(
        "Scottcjn/Rustchain",
        "123",
        payment["id"],
        75.0,
        "contributor",
    )
    comments = [
        payment,
        {
            "id": 202,
            "user": {"login": "github-actions[bot]"},
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "body": f"<!-- RTC-AutoPay-Started payment_key={payment_key} payment_comment_id=101 -->",
        },
    ]
    transfer_calls = []
    comment_posts = []

    def fake_post(url, headers=None, json=None, timeout=None):
        assert json is not None
        if url.endswith("/git/refs"):
            return FakeResponse({"ref": json["ref"]}, status_code=201)
        if url.endswith("/wallet/transfer"):
            transfer_calls.append(json)
            return FakeResponse({"ok": True, "pending_id": "p1"})
        comment_posts.append(json["body"])
        return FakeResponse({"id": 999})

    with patch.dict(os.environ, base_env(), clear=True):
        auto_pay.requests.get = paged_comments(comments)
        auto_pay.requests.post = fake_post
        auto_pay.main()

    assert transfer_calls == []
    assert comment_posts == []


def test_atomic_lock_ref_blocks_two_runs_from_same_initial_comment_set():
    auto_pay = load_auto_pay()
    comments = [owner_payment_comment()]
    created_refs = set()
    transfer_calls = []
    comment_posts = []

    def fake_post(url, headers=None, json=None, timeout=None):
        assert json is not None
        if url.endswith("/git/refs"):
            ref = json["ref"]
            if ref in created_refs:
                return FakeResponse({"message": "Reference already exists"}, status_code=422)
            created_refs.add(ref)
            return FakeResponse({"ref": ref}, status_code=201)
        if url.endswith("/wallet/transfer"):
            transfer_calls.append(json)
            return FakeResponse({"ok": True, "pending_id": "p1"})
        comment_posts.append(json["body"])
        return FakeResponse({"id": 999})

    with patch.dict(os.environ, base_env(), clear=True):
        auto_pay.requests.get = paged_comments(comments)
        auto_pay.requests.post = fake_post

        # Both invocations observe the same initial comments. The second one is
        # stopped only by the atomic Git ref create, which mirrors the real
        # concurrent workflow race that comment pre-seeding did not exercise.
        auto_pay.main()
        auto_pay.main()

    assert len(created_refs) == 1
    assert len(transfer_calls) == 1
    assert len([body for body in comment_posts if "RTC-AutoPay-Started" in body]) == 1
    assert len([body for body in comment_posts if "RTC-AutoPay-Confirmed" in body]) == 1


def test_post_started_failure_releases_lock_before_raising():
    auto_pay = load_auto_pay()
    comments = [owner_payment_comment()]
    released_refs = []
    transfer_calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        assert json is not None
        if url.endswith("/git/refs"):
            return FakeResponse({"ref": json["ref"]}, status_code=201)
        if url.endswith("/wallet/transfer"):
            transfer_calls.append(json)
            return FakeResponse({"ok": True, "pending_id": "p1"})
        return FakeResponse(
            {"message": "temporary comment outage"},
            status_code=503,
            text="temporary comment outage",
            raise_http=True,
        )

    def fake_delete(url, headers=None, timeout=None):
        released_refs.append(url)
        return FakeResponse(status_code=204)

    with patch.dict(os.environ, base_env(), clear=True):
        auto_pay.requests.get = paged_comments(comments)
        auto_pay.requests.post = fake_post
        auto_pay.requests.delete = fake_delete
        with pytest.raises(HTTPError):
            auto_pay.main()

    assert transfer_calls == []
    assert len(released_refs) == 1
    assert "/git/refs/heads/rtc-autopay-locks/pr-123/" in released_refs[0]


def test_lock_create_non_exists_422_is_not_treated_as_in_progress():
    auto_pay = load_auto_pay()

    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse(
            {"message": "Object does not exist"},
            status_code=422,
            text="Object does not exist",
            raise_http=True,
        )

    with patch.dict(os.environ, base_env(), clear=True):
        auto_pay.requests.get = paged_comments([])
        auto_pay.requests.post = fake_post
        with pytest.raises(HTTPError):
            auto_pay.acquire_payment_lock("Scottcjn/Rustchain", "123", "key")


def test_lock_create_missing_contents_write_403_raises():
    auto_pay = load_auto_pay()

    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse(
            {"message": "Resource not accessible by integration"},
            status_code=403,
            text="Resource not accessible by integration",
            raise_http=True,
        )

    with patch.dict(os.environ, base_env(), clear=True):
        auto_pay.requests.get = paged_comments([])
        auto_pay.requests.post = fake_post
        with pytest.raises(HTTPError):
            auto_pay.acquire_payment_lock("Scottcjn/Rustchain", "123", "key")


def test_resolve_lock_sha_uses_base_default_branch_not_github_sha():
    auto_pay = load_auto_pay()
    get_calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        get_calls.append(url)
        if url.endswith("/repos/Scottcjn/Rustchain"):
            return FakeResponse({"default_branch": "trunk"})
        if url.endswith("/git/ref/heads/trunk"):
            return FakeResponse({"object": {"sha": "abcdef0123456789abcdef0123456789abcdef01"}})
        return FakeResponse({}, status_code=404, raise_http=True)

    env = base_env()
    env["GITHUB_SHA"] = "ffffffffffffffffffffffffffffffffffffffff"
    with patch.dict(os.environ, env, clear=True):
        auto_pay.requests.get = fake_get
        assert auto_pay.resolve_lock_sha("Scottcjn/Rustchain") == "abcdef0123456789abcdef0123456789abcdef01"

    assert get_calls == [
        "https://api.github.com/repos/Scottcjn/Rustchain",
        "https://api.github.com/repos/Scottcjn/Rustchain/git/ref/heads/trunk",
    ]


def test_stale_started_marker_does_not_block_retry():
    auto_pay = load_auto_pay()
    payment = owner_payment_comment()
    payment_key = auto_pay.build_payment_key(
        "Scottcjn/Rustchain",
        "123",
        payment["id"],
        75.0,
        "contributor",
    )
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=auto_pay.STARTED_LOCK_TTL_SECONDS + 1)
    comments = [
        payment,
        {
            "id": 202,
            "user": {"login": "github-actions[bot]"},
            "created_at": stale_time.isoformat().replace("+00:00", "Z"),
            "body": f"<!-- RTC-AutoPay-Started payment_key={payment_key} payment_comment_id=101 -->",
        },
    ]
    transfer_calls = []
    comment_posts = []

    def fake_post(url, headers=None, json=None, timeout=None):
        assert json is not None
        if url.endswith("/git/refs"):
            return FakeResponse({"ref": json["ref"]}, status_code=201)
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
    assert any("RTC-AutoPay-Confirmed" in body for body in comment_posts)


def test_manual_transfer_notice_does_not_block_later_auto_pay():
    auto_pay = load_auto_pay()
    persisted_comments = [owner_payment_comment()]
    transfer_calls = []
    comment_posts = []

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/repos/Scottcjn/Rustchain"):
            return FakeResponse({"default_branch": "main"})
        if url.endswith("/git/ref/heads/main"):
            return FakeResponse({"object": {"sha": "abcdef0123456789abcdef0123456789abcdef01"}})
        page = (params or {}).get("page", 1)
        return FakeResponse(persisted_comments if page == 1 else [])

    def fake_post(url, headers=None, json=None, timeout=None):
        assert json is not None
        if url.endswith("/git/refs"):
            return FakeResponse({"ref": json["ref"]}, status_code=201)
        if url.endswith("/wallet/transfer"):
            transfer_calls.append(json)
            return FakeResponse({"ok": True, "pending_id": "p1"})

        body = json["body"]
        comment_posts.append(body)
        persisted_comments.append({
            "id": 200 + len(comment_posts),
            "user": {"login": "github-actions[bot]"},
            "body": body,
        })
        return FakeResponse({"id": 200 + len(comment_posts)})

    no_secrets_env = base_env()
    no_secrets_env["RTC_VPS_HOST"] = ""
    no_secrets_env["RTC_ADMIN_KEY"] = ""

    with patch.dict(os.environ, no_secrets_env, clear=True):
        auto_pay.requests.get = fake_get
        auto_pay.requests.post = fake_post
        auto_pay.main()
        auto_pay.main()

    with patch.dict(os.environ, base_env(), clear=True):
        auto_pay.requests.get = fake_get
        auto_pay.requests.post = fake_post
        auto_pay.main()

    assert len([body for body in comment_posts if "RTC-AutoPay-Manual-Required" in body]) == 1
    assert len(transfer_calls) == 1
    assert any("RTC-AutoPay-Confirmed" in body for body in comment_posts)


def test_legacy_manual_transfer_notice_does_not_block_later_auto_pay():
    auto_pay = load_auto_pay()
    comments = [owner_payment_comment()]
    payment_key = auto_pay.build_payment_key(
        "Scottcjn/Rustchain",
        "123",
        101,
        75.0,
        "contributor",
    )
    comments.append({
        "id": 202,
        "user": {"login": "github-actions[bot]"},
        "body": f"<!-- RTC-AutoPay-Confirmed:MANUAL payment_key={payment_key} -->",
    })
    transfer_calls = []
    comment_posts = []

    def fake_post(url, headers=None, json=None, timeout=None):
        assert json is not None
        if url.endswith("/git/refs"):
            return FakeResponse({"ref": json["ref"]}, status_code=201)
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
    assert any("RTC-AutoPay-Confirmed" in body for body in comment_posts)


def test_github_comment_api_calls_use_timeout():
    auto_pay = load_auto_pay()
    get_calls = []
    post_calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        get_calls.append((url, params, timeout))
        return FakeResponse([])

    def fake_post(url, headers=None, json=None, timeout=None):
        post_calls.append((url, json, timeout))
        return FakeResponse({"id": 999})

    with patch.dict(os.environ, base_env(), clear=True):
        auto_pay.requests.get = fake_get
        auto_pay.requests.post = fake_post

        assert auto_pay.fetch_pr_comments("Scottcjn/Rustchain", "123") == []
        auto_pay.post_comment("Scottcjn/Rustchain", "123", "paid")

    assert get_calls == [
        (
            "https://api.github.com/repos/Scottcjn/Rustchain/issues/123/comments",
            {"per_page": 100, "page": 1},
            auto_pay.GITHUB_REQUEST_TIMEOUT_SECONDS,
        )
    ]
    assert post_calls == [
        (
            "https://api.github.com/repos/Scottcjn/Rustchain/issues/123/comments",
            {"body": "paid"},
            auto_pay.GITHUB_REQUEST_TIMEOUT_SECONDS,
        )
    ]
