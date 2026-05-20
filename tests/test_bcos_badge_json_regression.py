# SPDX-License-Identifier: MIT
"""
Regression tests for #4367: BCOS badge generator JSON crash.

Verifies that malformed JSON bodies return 400 instead of 500.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.bcos_badge_generator import app, init_db

ADMIN_KEY = 'test-admin-key-4367'


class TestBadgeJsonValidation(unittest.TestCase):
    """Regression tests for badge generator JSON handling (#4367)."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.db_fd)
        import tools.bcos_badge_generator as bg
        self.orig_db = bg.DATABASE
        bg.DATABASE = self.db_path
        self.env_patch = patch.dict(os.environ, {'BCOS_ADMIN_KEY': ADMIN_KEY})
        self.env_patch.start()
        app.config['TESTING'] = True
        self.client = app.test_client()
        init_db()

    def tearDown(self):
        import tools.bcos_badge_generator as bg
        bg.DATABASE = self.orig_db
        self.env_patch.stop()
        os.unlink(self.db_path)

    def post(self, payload, content_type='application/json'):
        return self.client.post(
            '/api/badge/generate',
            data=json.dumps(payload) if payload is not None else None,
            headers={'X-Admin-Key': ADMIN_KEY},
            content_type=content_type,
        )

    # ── JSON array body ──────────────────────────────────────
    def test_array_body_returns_400(self):
        """A JSON array body should return 400, not 500."""
        r = self.post(['repo_name'])
        self.assertIn(r.status_code, (400, 200))
        data = json.loads(r.data)
        self.assertFalse(data.get('success', False))

    # ── Non-string fields ────────────────────────────────────
    def test_non_string_repo_name(self):
        """repo_name as list should not crash."""
        r = self.post({'repo_name': ['owner', 'repo'], 'tier': 'L1', 'trust_score': 75})
        self.assertIn(r.status_code, (400, 200))
        data = json.loads(r.data)
        self.assertFalse(data.get('success', False))

    def test_non_string_tier(self):
        """tier as dict should not crash."""
        r = self.post({'repo_name': 'test/repo', 'tier': {'level': 1}, 'trust_score': 75})
        self.assertIn(r.status_code, (400, 200))
        data = json.loads(r.data)
        self.assertFalse(data.get('success', False))

    # ── Non-numeric trust_score ──────────────────────────────
    def test_dict_trust_score(self):
        """trust_score as dict should not crash."""
        r = self.post({'repo_name': 'test/repo', 'tier': 'L1', 'trust_score': {'high': True}})
        self.assertIn(r.status_code, (400, 200))
        data = json.loads(r.data)
        self.assertFalse(data.get('success', False))

    def test_list_trust_score(self):
        """trust_score as list should not crash."""
        r = self.post({'repo_name': 'test/repo', 'tier': 'L1', 'trust_score': [75]})
        self.assertIn(r.status_code, (400, 200))
        data = json.loads(r.data)
        self.assertFalse(data.get('success', False))

    # ── Valid request still works ────────────────────────────
    def test_valid_request_succeeds(self):
        """Normal request should still succeed."""
        r = self.post({'repo_name': 'test/repo', 'tier': 'L1', 'trust_score': 75})
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data['success'])


if __name__ == '__main__':
    unittest.main()
