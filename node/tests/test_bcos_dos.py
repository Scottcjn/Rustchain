import unittest
from flask import Flask
from node.bcos_routes import bcos_bp, _DB_PATH
import sqlite3
import os

class TestBCOSDoS(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(bcos_bp)
        self.client = self.app.test_client()
        
        # Use a temporary DB for testing
        self.test_db = "test_bcos.db"
        import node.bcos_routes
        node.bcos_routes._DB_PATH = self.test_db
        
        with sqlite3.connect(self.test_db) as conn:
            from node.bcos_routes import init_bcos_table
            init_bcos_table(conn)
            conn.commit()

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_field_length_limits(self):
        # Test that extremely long fields are rejected (DoS prevention)
        long_id = "A" * 1000
        payload = {
            "report": {
                "cert_id": long_id,
                "commitment": "hash",
                "repo": "org/repo",
                "commit_sha": "sha",
                "reviewer": "rev",
                "trust_score": 80
            },
            "signature": "sig",
            "signer_pubkey": "pk"
        }
        # Note: In a real scenario, we'd need to handle auth. 
        # For this test, we bypass it by using X-Admin-Key if configured or 
        # by mocking the auth check.
        
        response = self.client.post("/bcos/attest", 
                                   json=payload, 
                                   headers={"X-Admin-Key": "mock_key"})
        
        # If admin key doesn't match, it returns 401, but the length check 
        # happens BEFORE auth in some versions, or after. 
        # In the current code, auth is checked FIRST (line 324).
        # So we must provide a valid admin key for the test to reach the length check.
        
        # Let's set the environment variable for the test
        os.environ["RC_ADMIN_KEY"] = "mock_key"
        
        response = self.client.post("/bcos/attest", 
                                   json=payload, 
                                   headers={"X-Admin-Key": "mock_key"})
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("field_too_long", response.get_json()["error"])

if __name__ == "__main__":
    unittest.main()
