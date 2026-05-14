import os
import re
import sqlite3
import tempfile
from contextlib import closing

import pytest

# Module under test
import contributor_registry as cr

VALID_RTC_WALLET = "RTC019e78d600fb3131c29d7ba80aba8fe644be426e"
VALID_EVM_WALLET = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
REGISTRATION_TOKEN = "registration-token"
ADMIN_TOKEN = "admin-token"


def db_connect():
    return closing(sqlite3.connect(cr.DB_PATH))


@pytest.fixture
def app():
    """Create a test Flask app with a temporary database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    cr.DB_PATH = db_path
    cr.app.config["TESTING"] = True
    cr.app.config["CONTRIBUTOR_REGISTRATION_TOKEN"] = REGISTRATION_TOKEN
    cr.app.config["CONTRIBUTOR_ADMIN_TOKEN"] = ADMIN_TOKEN
    cr.init_db()
    yield cr.app
    os.close(db_fd)
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


def csrf_token(client):
    response = client.get("/")
    match = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
    assert match is not None
    return match.group(1).decode()


def registration_payload(client, **overrides):
    payload = {
        "csrf_token": csrf_token(client),
        "registration_token": REGISTRATION_TOKEN,
        "github_username": "newuser",
        "contributor_type": "agent",
        "rtc_wallet": VALID_RTC_WALLET,
        "contribution_history": "Mining and staking",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def seed_contributor(app):
    """Insert a test contributor into the database."""
    with db_connect() as conn:
        conn.execute(
            "INSERT INTO contributors (github_username, contributor_type, rtc_wallet, contribution_history, status) "
            "VALUES (?, ?, ?, ?, ?)",
            ("testuser", "human", VALID_RTC_WALLET, "PR reviews and bug reports", "approved"),
        )
        conn.commit()


class TestInitDb:
    def test_creates_table(self, app):
        """init_db should create the contributors table."""
        with db_connect() as conn:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='contributors'"
            ).fetchone()
        assert result is not None
        assert result[0] == "contributors"

    def test_idempotent(self, app):
        """Calling init_db twice should not raise."""
        cr.init_db()
        cr.init_db()


class TestIndexRoute:
    def test_index_returns_200(self, client):
        """GET / should return 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_index_shows_contributors(self, client, seed_contributor):
        """GET / should list registered contributors."""
        response = client.get("/")
        assert b"testuser" in response.data
        assert b"RTC019...426e" in response.data
        assert VALID_RTC_WALLET.encode() not in response.data


class TestRegisterRoute:
    def test_register_new_contributor(self, client):
        """POST /register should add a new contributor."""
        response = client.post("/register", data=registration_payload(client), follow_redirects=True)
        assert response.status_code == 200
        with db_connect() as conn:
            row = conn.execute(
                "SELECT contributor_type, status FROM contributors WHERE github_username='newuser'"
            ).fetchone()
        assert row is not None
        assert row[0] == "agent"
        assert row[1] == "pending"

    def test_register_duplicate_username(self, client, seed_contributor):
        """POST /register with existing username should flash error."""
        response = client.post(
            "/register",
            data=registration_payload(
                client,
                github_username="testuser",
                contributor_type="human",
                rtc_wallet=VALID_EVM_WALLET,
                contribution_history="",
            ),
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"already registered" in response.data

    def test_register_rejects_missing_csrf_token(self, client):
        """POST /register should reject form submissions without CSRF."""
        payload = registration_payload(client)
        payload.pop("csrf_token")
        response = client.post("/register", data=payload)
        assert response.status_code == 400

    def test_register_rejects_missing_registration_token(self, client):
        """POST /register should reject requests without the configured token."""
        response = client.post(
            "/register",
            data=registration_payload(client, registration_token=""),
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Invalid contributor registration token" in response.data

    def test_register_rejects_unconfigured_registration_token(self, app, client):
        """Deployments without a registration token should fail closed."""
        app.config["CONTRIBUTOR_REGISTRATION_TOKEN"] = ""
        response = client.post("/register", data=registration_payload(client), follow_redirects=True)
        assert response.status_code == 200
        assert b"registration is closed" in response.data

    def test_register_rejects_invalid_github_username(self, client):
        """POST /register should reject invalid GitHub username syntax."""
        response = client.post(
            "/register",
            data=registration_payload(client, github_username="-not-valid"),
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"valid GitHub username" in response.data

    def test_register_rejects_invalid_contributor_type(self, client):
        """POST /register should reject contributor types outside the allowlist."""
        response = client.post(
            "/register",
            data=registration_payload(client, contributor_type="miner"),
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"valid contributor type" in response.data

    def test_register_rejects_invalid_wallet(self, client):
        """POST /register should reject malformed wallet strings."""
        response = client.post(
            "/register",
            data=registration_payload(client, rtc_wallet="RTC0abc123"),
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"valid RTC or EVM wallet address" in response.data

    def test_register_accepts_leading_at_username(self, client):
        """POST /register should normalize common @username input."""
        response = client.post(
            "/register",
            data=registration_payload(client, github_username="@newuser"),
            follow_redirects=True,
        )
        assert response.status_code == 200
        with db_connect() as conn:
            row = conn.execute(
                "SELECT github_username FROM contributors WHERE github_username='newuser'"
            ).fetchone()
        assert row is not None


class TestApiContributors:
    def test_api_returns_json(self, client):
        """GET /api/contributors should return JSON."""
        response = client.get("/api/contributors")
        assert response.status_code == 200
        assert response.content_type == "application/json"

    def test_api_includes_registered_contributors(self, client, seed_contributor):
        """GET /api/contributors should list registered users."""
        response = client.get("/api/contributors")
        data = response.get_json()
        assert "contributors" in data
        usernames = [c["github_username"] for c in data["contributors"]]
        assert "testuser" in usernames

    def test_api_contributor_fields(self, client, seed_contributor):
        """Each contributor in API response should have expected fields."""
        response = client.get("/api/contributors")
        data = response.get_json()
        contrib = data["contributors"][0]
        for field in ("github_username", "type", "wallet", "registered", "status"):
            assert field in contrib

    def test_api_redacts_wallets(self, client, seed_contributor):
        """The public API should not expose full wallet addresses."""
        response = client.get("/api/contributors")
        data = response.get_json()
        contrib = data["contributors"][0]
        assert contrib["wallet"] == "RTC019...426e"
        assert contrib["wallet"] != VALID_RTC_WALLET


class TestApproveRoute:
    def test_approve_rejects_missing_admin_token(self, client):
        """GET /approve/<username> should require an admin token."""
        client.post(
            "/register",
            data=registration_payload(
                client,
                github_username="pendinguser",
                contributor_type="bot",
                contribution_history="",
            ),
            follow_redirects=True,
        )
        response = client.get("/approve/pendinguser", follow_redirects=True)
        assert response.status_code == 403
        with db_connect() as conn:
            row = conn.execute(
                "SELECT status FROM contributors WHERE github_username='pendinguser'"
            ).fetchone()
        assert row[0] == "pending"

    def test_approve_rejects_admin_token_in_query_string(self, client):
        """GET /approve/<username> should not accept admin secrets in URLs."""
        client.post(
            "/register",
            data=registration_payload(
                client,
                github_username="pendinguser",
                contributor_type="bot",
                contribution_history="",
            ),
            follow_redirects=True,
        )
        response = client.get(
            f"/approve/pendinguser?admin_token={ADMIN_TOKEN}",
            follow_redirects=True,
        )
        assert response.status_code == 403
        with db_connect() as conn:
            row = conn.execute(
                "SELECT status FROM contributors WHERE github_username='pendinguser'"
            ).fetchone()
        assert row[0] == "pending"

    def test_approve_pending_contributor(self, client):
        """GET /approve/<username> with admin token should set status to approved."""
        client.post(
            "/register",
            data=registration_payload(
                client,
                github_username="pendinguser",
                contributor_type="bot",
                contribution_history="",
            ),
            follow_redirects=True,
        )
        response = client.get(
            "/approve/pendinguser",
            headers={"X-Admin-Token": ADMIN_TOKEN},
            follow_redirects=True,
        )
        assert response.status_code == 200
        with db_connect() as conn:
            row = conn.execute(
                "SELECT status FROM contributors WHERE github_username='pendinguser'"
            ).fetchone()
        assert row[0] == "approved"

    def test_route_requests_release_temp_database_file(self, app, client):
        """Route-level database handles should not block temp DB cleanup on Windows."""
        client.post(
            "/register",
            data=registration_payload(client, github_username="cleanupuser"),
            follow_redirects=True,
        )
        response = client.get(
            "/approve/cleanupuser",
            headers={"X-Admin-Token": ADMIN_TOKEN},
            follow_redirects=True,
        )
        assert response.status_code == 200

        cleanup_path = cr.DB_PATH
        cr.DB_PATH = os.path.join(tempfile.gettempdir(), "unused-contributor-test.db")
        os.unlink(cleanup_path)
        assert not os.path.exists(cleanup_path)


class TestDatabaseConstraints:
    def test_unique_username_constraint(self, app):
        """Inserting duplicate github_username should raise IntegrityError."""
        with db_connect() as conn:
            conn.execute(
                "INSERT INTO contributors (github_username, contributor_type, rtc_wallet) VALUES (?, ?, ?)",
                ("unique-test", "human", VALID_RTC_WALLET),
            )
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO contributors (github_username, contributor_type, rtc_wallet) VALUES (?, ?, ?)",
                    ("unique-test", "agent", VALID_EVM_WALLET),
                )

    def test_default_status_is_pending(self, client):
        """New registrations should have status=pending by default."""
        client.post(
            "/register",
            data=registration_payload(
                client,
                github_username="defaultstatus",
                contributor_type="human",
            ),
            follow_redirects=True,
        )
        with db_connect() as conn:
            row = conn.execute(
                "SELECT status FROM contributors WHERE github_username='defaultstatus'"
            ).fetchone()
        assert row[0] == "pending"
