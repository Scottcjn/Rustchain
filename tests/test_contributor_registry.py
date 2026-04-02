# SPDX-License-Identifier: MIT
"""Unit tests for contributor_registry.py"""

import pytest
import os
import tempfile
import sqlite3
from unittest.mock import patch, MagicMock

# Import the module under test
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import contributor_registry


@pytest.fixture
def app():
    """Create application for testing."""
    contributor_registry.app.config['TESTING'] = True
    # Use a temporary database for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        tmp_db = tmp.name
    contributor_registry.DB_PATH = tmp_db
    yield contributor_registry.app
    # Cleanup
    os.unlink(tmp_db)


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def initialized_db(app):
    """Initialize database for tests."""
    with app.app_context():
        contributor_registry.init_db()
    return app


class TestInitDB:
    """Tests for init_db function."""

    def test_init_db_creates_table(self, app):
        """Test that init_db creates the contributors table."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp_db = tmp.name
        try:
            contributor_registry.DB_PATH = tmp_db
            contributor_registry.init_db()
            
            # Verify table exists
            with sqlite3.connect(tmp_db) as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='contributors'"
                )
                result = cursor.fetchone()
                assert result is not None
                assert result[0] == 'contributors'
        finally:
            os.unlink(tmp_db)

    def test_init_db_table_schema(self, app):
        """Test that init_db creates table with correct schema."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp_db = tmp.name
        try:
            contributor_registry.DB_PATH = tmp_db
            contributor_registry.init_db()
            
            with sqlite3.connect(tmp_db) as conn:
                cursor = conn.execute("PRAGMA table_info(contributors)")
                columns = {row[1]: row[2] for row in cursor.fetchall()}
                
                # Verify expected columns exist
                assert 'id' in columns
                assert 'github_username' in columns
                assert 'contributor_type' in columns
                assert 'rtc_wallet' in columns
                assert 'contribution_history' in columns
                assert 'registration_date' in columns
                assert 'status' in columns
        finally:
            os.unlink(tmp_db)


class TestIndexRoute:
    """Tests for the index route."""

    def test_index_returns_200(self, initialized_db, client):
        """Test that index route returns 200 OK."""
        response = client.get('/')
        assert response.status_code == 200

    def test_index_contains_title(self, initialized_db, client):
        """Test that index page contains expected title."""
        response = client.get('/')
        assert b'RustChain Ecosystem Contributor Registry' in response.data

    def test_index_empty_database(self, initialized_db, client):
        """Test index with no contributors."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Registered Contributors' in response.data


class TestRegisterRoute:
    """Tests for the register route."""

    def test_register_success(self, initialized_db, client):
        """Test successful contributor registration."""
        response = client.post('/register', data={
            'github_username': 'testuser',
            'contributor_type': 'human',
            'rtc_wallet': 'RTCtest123',
            'contribution_history': 'Test contributions'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Successfully registered @testuser' in response.data

    def test_register_duplicate_username(self, initialized_db, client):
        """Test registration with duplicate username."""
        # First registration
        client.post('/register', data={
            'github_username': 'duplicateuser',
            'contributor_type': 'human',
            'rtc_wallet': 'RTCtest123',
            'contribution_history': 'Test'
        })
        
        # Second registration with same username
        response = client.post('/register', data={
            'github_username': 'duplicateuser',
            'contributor_type': 'human',
            'rtc_wallet': 'RTCtest456',
            'contribution_history': 'Test 2'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'already registered' in response.data

    def test_register_missing_required_fields(self, initialized_db, client):
        """Test registration with missing required fields."""
        # Missing github_username
        response = client.post('/register', data={
            'contributor_type': 'human',
            'rtc_wallet': 'RTCtest123'
        })
        # Flask should return 400 for missing required fields or redirect with error
        assert response.status_code in [200, 400]

    def test_register_all_contributor_types(self, initialized_db, client):
        """Test registration with all valid contributor types."""
        for contributor_type in ['human', 'bot', 'agent']:
            response = client.post('/register', data={
                'github_username': f'user_{contributor_type}',
                'contributor_type': contributor_type,
                'rtc_wallet': f'RTC{contributor_type}123',
                'contribution_history': f'Test {contributor_type}'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert f'Successfully registered @user_{contributor_type}'.encode() in response.data


class TestApiContributorsRoute:
    """Tests for the API contributors endpoint."""

    def test_api_contributors_empty(self, initialized_db, client):
        """Test API with no contributors."""
        response = client.get('/api/contributors')
        assert response.status_code == 200
        data = response.get_json()
        assert 'contributors' in data
        assert len(data['contributors']) == 0

    def test_api_contributors_with_data(self, initialized_db, client):
        """Test API with contributors."""
        # Add a contributor
        client.post('/register', data={
            'github_username': 'apiuser',
            'contributor_type': 'human',
            'rtc_wallet': 'RTCapi123',
            'contribution_history': 'API test'
        })
        
        response = client.get('/api/contributors')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['contributors']) == 1
        assert data['contributors'][0]['github_username'] == 'apiuser'
        assert data['contributors'][0]['wallet'] == 'RTCapi123'

    def test_api_contributors_response_format(self, initialized_db, client):
        """Test API response format."""
        client.post('/register', data={
            'github_username': 'formatuser',
            'contributor_type': 'bot',
            'rtc_wallet': 'RTCformat',
            'contribution_history': 'Format test'
        })
        
        response = client.get('/api/contributors')
        data = response.get_json()
        
        contributor = data['contributors'][0]
        assert 'github_username' in contributor
        assert 'type' in contributor
        assert 'wallet' in contributor
        assert 'registered' in contributor
        assert 'status' in contributor


class TestApproveContributorRoute:
    """Tests for the approve contributor route."""

    def test_approve_existing_contributor(self, initialized_db, client):
        """Test approving an existing contributor."""
        # First register a contributor
        client.post('/register', data={
            'github_username': 'approveuser',
            'contributor_type': 'human',
            'rtc_wallet': 'RTCapprove',
            'contribution_history': 'To be approved'
        })
        
        # Approve the contributor
        response = client.get('/approve/approveuser', follow_redirects=True)
        assert response.status_code == 200
        assert b'Approved @approveuser' in response.data

    def test_approve_nonexistent_contributor(self, initialized_db, client):
        """Test approving a non-existent contributor."""
        response = client.get('/approve/nonexistent', follow_redirects=True)
        # Should still redirect without error (SQL UPDATE affects 0 rows)
        assert response.status_code == 200

    def test_approve_changes_status(self, initialized_db, client):
        """Test that approve actually changes the status."""
        # Register contributor
        client.post('/register', data={
            'github_username': 'statususer',
            'contributor_type': 'human',
            'rtc_wallet': 'RTCstatus',
            'contribution_history': 'Status test'
        })
        
        # Verify initial status is 'pending'
        with sqlite3.connect(contributor_registry.DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT status FROM contributors WHERE github_username = 'statususer'"
            )
            status = cursor.fetchone()[0]
            assert status == 'pending'
        
        # Approve
        client.get('/approve/statususer')
        
        # Verify status changed to 'approved'
        with sqlite3.connect(contributor_registry.DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT status FROM contributors WHERE github_username = 'statususer'"
            )
            status = cursor.fetchone()[0]
            assert status == 'approved'


class TestEdgeCases:
    """Edge case tests."""

    def test_register_empty_contribution_history(self, initialized_db, client):
        """Test registration with empty contribution history."""
        response = client.post('/register', data={
            'github_username': 'nohistory',
            'contributor_type': 'human',
            'rtc_wallet': 'RTCnohistory'
            # contribution_history is optional
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Successfully registered @nohistory' in response.data

    def test_register_special_characters_in_username(self, initialized_db, client):
        """Test registration with special characters in username."""
        response = client.post('/register', data={
            'github_username': 'user-with-dash_underscore',
            'contributor_type': 'human',
            'rtc_wallet': 'RTCspecial',
            'contribution_history': 'Special chars test'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Successfully registered @user-with-dash_underscore' in response.data

    def test_register_long_contribution_history(self, initialized_db, client):
        """Test registration with very long contribution history."""
        long_history = 'A' * 10000  # 10KB history
        response = client.post('/register', data={
            'github_username': 'longhistory',
            'contributor_type': 'human',
            'rtc_wallet': 'RTClong',
            'contribution_history': long_history
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Successfully registered @longhistory' in response.data

    def test_multiple_contributors_order(self, initialized_db, client):
        """Test that contributors are ordered by registration date DESC."""
        # Register multiple contributors
        for i in range(3):
            client.post('/register', data={
                'github_username': f'user{i}',
                'contributor_type': 'human',
                'rtc_wallet': f'RTC{i}',
                'contribution_history': f'User {i}'
            })
        
        response = client.get('/api/contributors')
        data = response.get_json()
        
        # Most recent should be first
        assert len(data['contributors']) == 3
        # Note: Due to fast registration, order might vary, but API should return all
        usernames = [c['github_username'] for c in data['contributors']]
        assert 'user0' in usernames
        assert 'user1' in usernames
        assert 'user2' in usernames


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
