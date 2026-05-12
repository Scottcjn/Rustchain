import pytest
import sqlite3
import os
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

    def test_index_shows_contributors(self, client, seed_contributor):
        """GET / should list registered contributors."""
        response = client.get("/")
        assert b"testuser" in response.data
        assert b"RTC019e78d600fb3131c29d7ba80aba8fe644be426e" in response.data


class TestRegisterRoute:
    def test_register_new_contributor(self, client):
        """POST /register should add a new contributor."""
        response = client.post("/register", data={
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
            "github_username": "testuser",
            "contributor_type": "human",
            "rtc_wallet": "RTC0dup",
            "contribution_history": "",
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"already registered" in response.data


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


class TestApproveRoute:
    def test_approve_pending_contributor(self, client):
        """POST /approve/<username> with valid admin key should approve."""
        # Register a pending contributor
        client.post("/register", data={
            "github_username": "pendinguser",
            "contributor_type": "bot",
            "rtc_wallet": "RTC0pending",
            "contribution_history": "",
        }, follow_redirects=True)
        
        # First try without admin key (should get 503)
        response = client.post("/approve/pendinguser", follow_redirects=True)
        assert response.status_code == 503
        
        # Try with wrong admin key (should get 401)
        response = client.post(
            "/approve/pendinguser",
            headers={"X-Admin-Key": "wrong_key"},
            follow_redirects=True
        )
        assert response.status_code == 401
        
        # Now with valid admin key (should approve)
        with patch('os.environ.get') as mock_env:
            mock_env.return_value = 'test_admin_key_12345'
            response = client.post(
                "/approve/pendinguser",
                headers={"X-Admin-Key": "test_admin_key_12345"},
                follow_redirects=True
            )
            assert response.status_code == 200
            
            # Check database
            with sqlite3.connect(cr.DB_PATH) as conn:
                row = conn.execute(
                    "SELECT status FROM contributors WHERE github_username='pendinguser'"
                ).fetchone()
            assert row[0] == "approved"
    
    def test_approve_get_method_not_allowed(self, client):
        """GET /approve/<username> should return 405."""
        response = client.get("/approve/someuser")
        assert response.status_code == 405  # Method Not Allowed


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
            "github_username": "defaultstatus",
            "contributor_type": "human",
            "rtc_wallet": "RTC0default",
        }, follow_redirects=True)
        with sqlite3.connect(cr.DB_PATH) as conn:
            row = conn.execute(
                "SELECT status FROM contributors WHERE github_username='defaultstatus'"
            ).fetchone()
        assert row[0] == "pending"

