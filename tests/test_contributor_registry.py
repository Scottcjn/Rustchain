import pytest
import sqlite3
import os
import importlib
import tempfile
import time
from unittest.mock import patch, MagicMock

# Module under test
import contributor_registry as cr


REGISTRATION_KEY = "synth-test-registration-key"
VALID_RTC_WALLET = "RTC019e78d600fb3131c29d7ba80aba8fe644be426e"
VALID_EVM_WALLET = "0x019e78d600fb3131c29d7ba80aba8fe644be426e"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app(monkeypatch):
    """Create a test Flask app with a temporary database and a configured registration key."""
    monkeypatch.setenv("CONTRIBUTOR_REGISTRATION_KEY", REGISTRATION_KEY)
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    cr.DB_PATH = db_path
    cr.app.config["TESTING"] = True
    cr.init_db()
    yield cr.app
    for _ in range(5):
        try:
            os.unlink(db_path)
            break
        except PermissionError:
            time.sleep(0.05)


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def seed_contributor(app):
    """Insert a test contributor into the database."""
    with sqlite3.connect(cr.DB_PATH) as conn:
        conn.execute(
            "INSERT INTO contributors (github_username, contributor_type, rtc_wallet, contribution_history, status) "
            "VALUES (?, ?, ?, ?, ?)",
            ("testuser", "human", VALID_RTC_WALLET, "PR reviews and bug reports", "approved"),
        )
        conn.commit()


def _get_csrf_token(client) -> str:
    """Prime a session and extract the CSRF token from the registration form."""
    response = client.get("/")
    html = response.data.decode()
    # The token is rendered as: <input type="hidden" name="csrf_token" value="...">
    needle = 'name="csrf_token" value="'
    start = html.find(needle)
    assert start != -1, "CSRF token input not found in index HTML"
    start += len(needle)
    end = html.find('"', start)
    return html[start:end]


def _registration_payload(client, **overrides):
    """Build a complete, valid /register payload with CSRF + registration_key prefilled."""
    payload = {
        "csrf_token": _get_csrf_token(client),
        "registration_key": REGISTRATION_KEY,
        "github_username": "newuser",
        "contributor_type": "agent",
        "rtc_wallet": VALID_RTC_WALLET,
        "contribution_history": "Mining and staking",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------


class TestInitDb:
    def test_creates_table(self, app):
        with sqlite3.connect(cr.DB_PATH) as conn:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='contributors'"
            ).fetchone()
        assert result is not None
        assert result[0] == "contributors"

    def test_idempotent(self, app):
        cr.init_db()
        cr.init_db()


# ---------------------------------------------------------------------------
# Validators (regex + redaction)
# ---------------------------------------------------------------------------


class TestWalletValidation:
    def test_accepts_strict_rtc(self):
        assert cr.RTC_WALLET_RE.fullmatch(VALID_RTC_WALLET)

    def test_accepts_strict_evm(self):
        assert cr.EVM_WALLET_RE.fullmatch(VALID_EVM_WALLET)

    def test_rejects_hex_then_rtc_suffix(self):
        """Regression test for ethever #5082's permissive regex flaw."""
        bad = "019e78d600fb3131c29d7ba80aba8fe644be426eRTC"
        assert not cr.RTC_WALLET_RE.fullmatch(bad)
        assert not cr.EVM_WALLET_RE.fullmatch(bad)

    def test_rejects_too_short(self):
        assert not cr.RTC_WALLET_RE.fullmatch("RTC0pending")
        assert not cr.RTC_WALLET_RE.fullmatch("RTCabc")

    def test_rejects_non_hex(self):
        bad = "RTC" + "g" * 40
        assert not cr.RTC_WALLET_RE.fullmatch(bad)


class TestUsernameValidation:
    def test_accepts_simple(self):
        assert cr.GITHUB_USERNAME_RE.fullmatch("octocat")

    def test_accepts_hyphen(self):
        assert cr.GITHUB_USERNAME_RE.fullmatch("octo-cat")

    def test_rejects_leading_hyphen(self):
        assert not cr.GITHUB_USERNAME_RE.fullmatch("-octocat")

    def test_rejects_trailing_hyphen(self):
        assert not cr.GITHUB_USERNAME_RE.fullmatch("octocat-")

    def test_rejects_empty(self):
        assert not cr.GITHUB_USERNAME_RE.fullmatch("")

    def test_rejects_overlong(self):
        # GitHub usernames are at most 39 chars
        assert not cr.GITHUB_USERNAME_RE.fullmatch("a" * 40)


class TestRedactWallet:
    def test_redacts_long(self):
        assert cr.redact_wallet(VALID_RTC_WALLET) == "RTC019...426e"

    def test_redacts_short(self):
        assert cr.redact_wallet("short") == "redacted"

    def test_empty(self):
        assert cr.redact_wallet("") == ""


# ---------------------------------------------------------------------------
# Index / display
# ---------------------------------------------------------------------------


class TestIndexRoute:
    def test_index_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_index_redacts_wallets(self, client, seed_contributor):
        """Public HTML must not expose full wallet addresses."""
        response = client.get("/")
        assert b"testuser" in response.data
        # Full wallet should NOT be present
        assert VALID_RTC_WALLET.encode() not in response.data
        # Redacted form SHOULD be present
        assert b"RTC019...426e" in response.data

    def test_index_renders_csrf_token(self, client):
        """The form must contain a CSRF token."""
        response = client.get("/")
        assert b'name="csrf_token"' in response.data


# ---------------------------------------------------------------------------
# /register — auth & validation
# ---------------------------------------------------------------------------


class TestRegisterCSRF:
    def test_register_without_csrf_returns_400(self, client):
        """Missing CSRF token → 400 BadRequest."""
        response = client.post("/register", data={
            "registration_key": REGISTRATION_KEY,
            "github_username": "newuser",
            "contributor_type": "agent",
            "rtc_wallet": VALID_RTC_WALLET,
        })
        assert response.status_code == 400

    def test_register_with_wrong_csrf_returns_400(self, client):
        # Prime a session
        client.get("/")
        response = client.post("/register", data={
            "csrf_token": "not-the-token",
            "registration_key": REGISTRATION_KEY,
            "github_username": "newuser",
            "contributor_type": "agent",
            "rtc_wallet": VALID_RTC_WALLET,
        })
        assert response.status_code == 400


class TestRegisterKey:
    def test_register_unconfigured_returns_503(self, client, monkeypatch):
        """Without CONTRIBUTOR_REGISTRATION_KEY env var → 503 service unavailable."""
        monkeypatch.delenv("CONTRIBUTOR_REGISTRATION_KEY", raising=False)
        payload = _registration_payload(client)
        response = client.post("/register", data=payload)
        assert response.status_code == 503

    def test_register_missing_key_returns_401(self, client):
        payload = _registration_payload(client, registration_key="")
        response = client.post("/register", data=payload)
        assert response.status_code == 401

    def test_register_wrong_key_returns_401(self, client):
        payload = _registration_payload(client, registration_key="not-the-key")
        response = client.post("/register", data=payload)
        assert response.status_code == 401

    def test_register_header_key_accepted(self, client):
        """X-Registration-Key header is equivalent to the form field."""
        payload = _registration_payload(client, registration_key="")
        response = client.post(
            "/register",
            data=payload,
            headers={"X-Registration-Key": REGISTRATION_KEY},
            follow_redirects=True,
        )
        assert response.status_code == 200


class TestRegisterValidation:
    def test_register_rejects_invalid_username(self, client):
        payload = _registration_payload(client, github_username="-bad-leading")
        response = client.post("/register", data=payload)
        assert response.status_code == 400

    def test_register_rejects_invalid_type(self, client):
        payload = _registration_payload(client, contributor_type="hacker")
        response = client.post("/register", data=payload)
        assert response.status_code == 400

    def test_register_rejects_invalid_wallet(self, client):
        payload = _registration_payload(client, rtc_wallet="not-a-wallet")
        response = client.post("/register", data=payload)
        assert response.status_code == 400

    def test_register_rejects_ethever_flaw_wallet(self, client):
        """Wallet of form `40-hex + RTC` (suffix) must be rejected."""
        payload = _registration_payload(
            client,
            rtc_wallet="019e78d600fb3131c29d7ba80aba8fe644be426eRTC",
        )
        response = client.post("/register", data=payload)
        assert response.status_code == 400

    def test_register_strips_at_prefix(self, client):
        """@username should be normalized to username before insert."""
        payload = _registration_payload(client, github_username="@octocat")
        response = client.post("/register", data=payload, follow_redirects=True)
        assert response.status_code == 200
        with sqlite3.connect(cr.DB_PATH) as conn:
            row = conn.execute(
                "SELECT github_username FROM contributors WHERE github_username='octocat'"
            ).fetchone()
        assert row is not None


class TestRegisterHappyPath:
    def test_register_new_contributor(self, client):
        payload = _registration_payload(client)
        response = client.post("/register", data=payload, follow_redirects=True)
        assert response.status_code == 200
        with sqlite3.connect(cr.DB_PATH) as conn:
            row = conn.execute(
                "SELECT contributor_type, status FROM contributors WHERE github_username='newuser'"
            ).fetchone()
        assert row is not None
        assert row[0] == "agent"
        assert row[1] == "pending"

    def test_register_truncates_long_history(self, client):
        payload = _registration_payload(client, contribution_history="x" * 5000)
        response = client.post("/register", data=payload, follow_redirects=True)
        assert response.status_code == 200
        with sqlite3.connect(cr.DB_PATH) as conn:
            row = conn.execute(
                "SELECT length(contribution_history) FROM contributors WHERE github_username='newuser'"
            ).fetchone()
        assert row[0] == cr.CONTRIBUTION_HISTORY_MAX

    def test_register_duplicate_username(self, client, seed_contributor):
        """POST /register with existing username should flash error, not crash."""
        payload = _registration_payload(client, github_username="testuser")
        response = client.post("/register", data=payload, follow_redirects=True)
        assert response.status_code == 200
        assert b"already registered" in response.data


# ---------------------------------------------------------------------------
# /api/contributors
# ---------------------------------------------------------------------------


class TestApiContributors:
    def test_api_returns_json(self, client):
        response = client.get("/api/contributors")
        assert response.status_code == 200
        assert response.content_type == "application/json"

    def test_api_redacts_wallets(self, client, seed_contributor):
        """API must not expose full wallet addresses."""
        response = client.get("/api/contributors")
        data = response.get_json()
        contrib = data["contributors"][0]
        assert contrib["wallet"] != VALID_RTC_WALLET
        assert contrib["wallet"] == cr.redact_wallet(VALID_RTC_WALLET)

    def test_api_contributor_fields(self, client, seed_contributor):
        response = client.get("/api/contributors")
        data = response.get_json()
        contrib = data["contributors"][0]
        for field in ("github_username", "type", "wallet", "registered", "status"):
            assert field in contrib


# ---------------------------------------------------------------------------
# /approve (already on main from saim256 #4723)
# ---------------------------------------------------------------------------


class TestApproveRoute:
    def test_approve_rejects_get(self, client):
        response = client.get("/approve/pendinguser")
        assert response.status_code == 405

    def test_approve_fails_closed_without_admin_key(self, client, monkeypatch):
        monkeypatch.delenv("CONTRIBUTOR_ADMIN_KEY", raising=False)
        with sqlite3.connect(cr.DB_PATH) as conn:
            conn.execute(
                "INSERT INTO contributors (github_username, contributor_type, rtc_wallet) VALUES (?, ?, ?)",
                ("pendinguser", "bot", VALID_RTC_WALLET),
            )
            conn.commit()
        response = client.post(
            "/approve/pendinguser",
            headers={"X-Admin-Key": "anything"},
            follow_redirects=True,
        )
        assert response.status_code == 401
        with sqlite3.connect(cr.DB_PATH) as conn:
            row = conn.execute(
                "SELECT status FROM contributors WHERE github_username='pendinguser'"
            ).fetchone()
        assert row[0] == "pending"

    def test_approve_with_admin_key(self, client, monkeypatch):
        monkeypatch.setenv("CONTRIBUTOR_ADMIN_KEY", "expected-admin-key")
        with sqlite3.connect(cr.DB_PATH) as conn:
            conn.execute(
                "INSERT INTO contributors (github_username, contributor_type, rtc_wallet) VALUES (?, ?, ?)",
                ("pendinguser", "bot", VALID_RTC_WALLET),
            )
            conn.commit()
        response = client.post(
            "/approve/pendinguser",
            headers={"X-Admin-Key": "expected-admin-key"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        with sqlite3.connect(cr.DB_PATH) as conn:
            row = conn.execute(
                "SELECT status FROM contributors WHERE github_username='pendinguser'"
            ).fetchone()
        assert row[0] == "approved"


# ---------------------------------------------------------------------------
# SECRET_KEY env var behavior
# ---------------------------------------------------------------------------


class TestSecretKeyConfiguration:
    def test_known_placeholder_secret_fails_closed(self, monkeypatch):
        original_secret = os.environ.get("CONTRIBUTOR_SECRET_KEY")
        try:
            monkeypatch.setenv("CONTRIBUTOR_SECRET_KEY", "rustchain_contributor_secret_2024")
            with pytest.raises(ValueError, match="known placeholder"):
                importlib.reload(cr)
        finally:
            if original_secret is None:
                monkeypatch.delenv("CONTRIBUTOR_SECRET_KEY", raising=False)
            else:
                monkeypatch.setenv("CONTRIBUTOR_SECRET_KEY", original_secret)
            importlib.reload(cr)
