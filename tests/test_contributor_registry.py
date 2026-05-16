import pytest
import sqlite3
import os
import importlib
import tempfile
from unittest.mock import patch, MagicMock

# Module under test
import contributor_registry as cr


@pytest.fixture
def app():
    """Create a test Flask app with a temporary database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    cr.DB_PATH = db_path
    cr.app.config["TESTING"] = True
    cr.init_db()
    yield cr.app
    os.close(db_fd)
    os.unlink(db_path)


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
            ("testuser", "human", "RTC019e78d600fb3131c29d7ba80aba8fe644be426e", "PR reviews and bug reports", "approved"),
        )
        conn.commit()


def csrf_token_for(client):
    client.get("/")
    with client.session_transaction() as sess:
        return sess["_csrf_token"]


class TestInitDb:
    def test_creates_table(self, app):
        """init_db should create the contributors table."""
        with sqlite3.connect(cr.DB_PATH) as conn:
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
        assert b"csrf_token" in response.data

    def test_index_shows_contributors(self, client, seed_contributor):
        """GET / should list registered contributors."""
        response = client.get("/")
        assert b"testuser" in response.data
        assert b"RTC019...426e" in response.data
        assert b"RTC019e78d600fb3131c29d7ba80aba8fe644be426e" not in response.data


class TestRegisterRoute:
    def test_register_new_contributor(self, client):
        """POST /register should add a new contributor."""
        response = client.post("/register", data={
            "csrf_token": csrf_token_for(client),
            "github_username": "newuser",
            "contributor_type": "agent",
            "rtc_wallet": "RTC0abc123",
            "contribution_history": "Mining and staking",
        }, follow_redirects=True)
        assert response.status_code == 200
        with sqlite3.connect(cr.DB_PATH) as conn:
            row = conn.execute(
                "SELECT contributor_type, status FROM contributors WHERE github_username='newuser'"
            ).fetchone()
        assert row is not None
        assert row[0] == "agent"
        assert row[1] == "pending"

    def test_register_duplicate_username(self, client, seed_contributor):
        """POST /register with existing username should flash error."""
        response = client.post("/register", data={
            "csrf_token": csrf_token_for(client),
            "github_username": "testuser",
            "contributor_type": "human",
            "rtc_wallet": "RTC0dup123",
            "contribution_history": "",
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"already registered" in response.data

    def test_register_rejects_invalid_username(self, client):
        response = client.post("/register", data={
            "csrf_token": csrf_token_for(client),
            "github_username": "bad username",
            "contributor_type": "human",
            "rtc_wallet": "RTC0abc123",
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Invalid GitHub username" in response.data

    def test_register_rejects_invalid_wallet(self, client):
        response = client.post("/register", data={
            "csrf_token": csrf_token_for(client),
            "github_username": "walletuser",
            "contributor_type": "human",
            "rtc_wallet": "not-a-wallet",
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Invalid RTC wallet" in response.data

    def test_register_rejects_missing_csrf(self, client):
        response = client.post("/register", data={
            "github_username": "nocsrf",
            "contributor_type": "human",
            "rtc_wallet": "RTC0abc123",
        })
        assert response.status_code == 400


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
        assert contrib["wallet"] == "RTC019...426e"


class TestApproveRoute:
    def test_approve_pending_contributor(self, client):
        """POST /approve/<username> should set status to approved."""
        client.post("/register", data={
            "csrf_token": csrf_token_for(client),
            "github_username": "pendinguser",
            "contributor_type": "bot",
            "rtc_wallet": "RTC0pending",
            "contribution_history": "",
        }, follow_redirects=True)
        response = client.post(
            "/approve/pendinguser",
            data={"csrf_token": csrf_token_for(client)},
            follow_redirects=True,
        )
        assert response.status_code == 200
        with sqlite3.connect(cr.DB_PATH) as conn:
            row = conn.execute(
                "SELECT status FROM contributors WHERE github_username='pendinguser'"
            ).fetchone()
        assert row[0] == "approved"

    def test_approve_rejects_missing_csrf(self, client):
        client.post("/register", data={
            "csrf_token": csrf_token_for(client),
            "github_username": "approvecsrf",
            "contributor_type": "human",
            "rtc_wallet": "RTC0approve",
        }, follow_redirects=True)
        response = client.post("/approve/approvecsrf")
        assert response.status_code == 400


class TestDatabaseConstraints:
    def test_unique_username_constraint(self, app):
        """Inserting duplicate github_username should raise IntegrityError."""
        with sqlite3.connect(cr.DB_PATH) as conn:
            conn.execute(
                "INSERT INTO contributors (github_username, contributor_type, rtc_wallet) VALUES (?, ?, ?)",
                ("unique_test", "human", "RTC0unique"),
            )
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO contributors (github_username, contributor_type, rtc_wallet) VALUES (?, ?, ?)",
                    ("unique_test", "agent", "RTC0dup2"),
                )

    def test_default_status_is_pending(self, client):
        """New registrations should have status=pending by default."""
        client.post("/register", data={
            "csrf_token": csrf_token_for(client),
            "github_username": "defaultstatus",
            "contributor_type": "human",
            "rtc_wallet": "RTC0default",
        }, follow_redirects=True)
        with sqlite3.connect(cr.DB_PATH) as conn:
            row = conn.execute(
                "SELECT status FROM contributors WHERE github_username='defaultstatus'"
            ).fetchone()
        assert row[0] == "pending"


class TestSecretKeyConfiguration:
    def test_known_placeholder_secret_fails_closed(self, monkeypatch):
        """The known compromised placeholder must not be accepted as a Flask secret."""
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
