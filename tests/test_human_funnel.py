# SPDX-License-Identifier: MIT

import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from human_funnel import app, init_db, get_db_path
from human_funnel import validate_referral_code, generate_brag_card_data
from human_funnel import calculate_hall_of_fame_rankings, process_micro_bounty_completion


class TestHumanFunnel(unittest.TestCase):

    def setUp(self):
        self.test_db = tempfile.NamedTemporaryFile(delete=False)
        self.test_db.close()
        self.db_path = self.test_db.name

        app.config['TESTING'] = True
        app.config['DATABASE'] = self.db_path
        self.client = app.test_client()

        with app.app_context():
            init_db()
            self._seed_test_data()

    def tearDown(self):
        os.unlink(self.db_path)

    def _seed_test_data(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO users (username, email, referral_code, referred_by, created_at, mining_setup_complete)
                VALUES
                ('alice123', 'alice@test.com', 'ALICE2024', NULL, '2024-01-15 10:30:00', 1),
                ('bob456', 'bob@test.com', 'BOBREF99', 'ALICE2024', '2024-01-16 11:45:00', 0),
                ('charlie789', 'charlie@test.com', 'CHAR1337', 'ALICE2024', '2024-01-17 09:15:00', 1)
            """)

            cursor.execute("""
                INSERT INTO micro_bounties (user_id, bounty_type, completed_at, reward_rtc)
                VALUES
                (1, 'social_share', '2024-01-15 12:00:00', 0.5),
                (1, 'profile_setup', '2024-01-15 13:30:00', 1.0),
                (3, 'social_share', '2024-01-17 14:22:00', 0.5)
            """)

            cursor.execute("""
                INSERT INTO brag_cards (user_id, total_earned_rtc, mining_days, referrals_count, card_image_path, generated_at)
                VALUES
                (1, 45.75, 12, 2, '/static/cards/alice_card.png', '2024-01-20 16:45:00')
            """)

            conn.commit()

    def test_landing_page_renders(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Start Your Mining Journey', response.data)
        self.assertIn(b'Get Mining in 3 Simple Steps', response.data)
        self.assertIn(b'Start Mining Now', response.data)

    def test_landing_page_hero_content(self):
        response = self.client.get('/')
        content = response.data.decode('utf-8')
        self.assertIn('Turn Your Old Computer Into Digital Gold', content)
        self.assertIn('No technical skills required', content)
        self.assertIn('Works on any hardware from 2010+', content)

    def test_registration_form_display(self):
        response = self.client.get('/register')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Create Your Account', response.data)
        self.assertIn(b'name="email"', response.data)
        self.assertIn(b'name="username"', response.data)
        self.assertIn(b'name="referral_code"', response.data)

    def test_user_registration_success(self):
        response = self.client.post('/register', data={
            'username': 'newuser',
            'email': 'new@test.com',
            'referral_code': 'ALICE2024'
        })
        self.assertEqual(response.status_code, 302)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, referred_by FROM users WHERE email = ?", ('new@test.com',))
            user = cursor.fetchone()
            self.assertIsNotNone(user)
            self.assertEqual(user[0], 'newuser')
            self.assertEqual(user[1], 'ALICE2024')

    def test_user_registration_invalid_referral(self):
        response = self.client.post('/register', data={
            'username': 'badref',
            'email': 'bad@test.com',
            'referral_code': 'INVALID99'
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Invalid referral code', response.data)

    def test_user_registration_duplicate_email(self):
        response = self.client.post('/register', data={
            'username': 'duplicate',
            'email': 'alice@test.com',
            'referral_code': ''
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Email already registered', response.data)

    def test_micro_bounty_list_display(self):
        response = self.client.get('/bounties')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Quick Tasks - Earn RTC Now!', response.data)
        self.assertIn(b'Share on Social Media', response.data)
        self.assertIn(b'Complete Profile Setup', response.data)
        self.assertIn(b'Refer a Friend', response.data)

    def test_micro_bounty_completion(self):
        response = self.client.post('/complete_bounty', json={
            'user_id': 2,
            'bounty_type': 'social_share',
            'proof_url': 'https://twitter.com/user/status/123'
        })
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertTrue(result['success'])
        self.assertEqual(result['reward_rtc'], 0.5)

    def test_micro_bounty_already_completed(self):
        response = self.client.post('/complete_bounty', json={
            'user_id': 1,
            'bounty_type': 'social_share',
            'proof_url': 'https://twitter.com/repeat/status/456'
        })
        self.assertEqual(response.status_code, 400)
        result = json.loads(response.data)
        self.assertFalse(result['success'])
        self.assertIn('already completed', result['error'])

    def test_referral_code_validation(self):
        valid_code = validate_referral_code('ALICE2024')
        self.assertTrue(valid_code)

        invalid_code = validate_referral_code('NOTFOUND')
        self.assertFalse(invalid_code)

    def test_referral_dashboard_display(self):
        response = self.client.get('/referrals/1')
        self.assertEqual(response.status_code, 200)
        content = response.data.decode('utf-8')
        self.assertIn('Your Referral Code: ALICE2024', content)
        self.assertIn('2 People Joined', content)
        self.assertIn('Invite More Friends', content)

    def test_brag_card_generation(self):
        response = self.client.post('/generate_brag_card', json={
            'user_id': 1
        })
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertTrue(result['success'])
        self.assertIn('card_url', result)
        self.assertEqual(result['stats']['total_earned'], 45.75)
        self.assertEqual(result['stats']['mining_days'], 12)

    def test_brag_card_data_calculation(self):
        card_data = generate_brag_card_data(1)
        self.assertEqual(card_data['total_earned_rtc'], 45.75)
        self.assertEqual(card_data['mining_days'], 12)
        self.assertEqual(card_data['referrals_count'], 2)
        self.assertIn('rank_text', card_data)

    def test_hall_of_fame_rankings(self):
        rankings = calculate_hall_of_fame_rankings()
        self.assertIsInstance(rankings, list)
        self.assertGreater(len(rankings), 0)
        self.assertEqual(rankings[0]['username'], 'alice123')
        self.assertIn('total_score', rankings[0])

    def test_hall_of_fame_page_display(self):
        response = self.client.get('/hall_of_fame')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Weekly Champions', response.data)
        self.assertIn(b'alice123', response.data)
        self.assertIn(b'Prize Pool: 50 RTC', response.data)

    def test_mining_setup_completion(self):
        response = self.client.post('/complete_mining_setup', json={
            'user_id': 2,
            'hardware_info': 'Intel i5-3470, 8GB RAM',
            'node_id': 'node_bob_001'
        })
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertTrue(result['success'])

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT mining_setup_complete FROM users WHERE id = ?", (2,))
            setup_complete = cursor.fetchone()[0]
            self.assertEqual(setup_complete, 1)

    def test_conversion_funnel_metrics(self):
        response = self.client.get('/api/funnel_metrics')
        self.assertEqual(response.status_code, 200)
        metrics = json.loads(response.data)
        self.assertIn('total_registrations', metrics)
        self.assertIn('setup_completion_rate', metrics)
        self.assertEqual(metrics['total_registrations'], 3)
        self.assertAlmostEqual(metrics['setup_completion_rate'], 66.67, places=1)

    def test_start_mining_button_flow(self):
        response = self.client.get('/start_mining')
        self.assertEqual(response.status_code, 200)
        content = response.data.decode('utf-8')
        self.assertIn('Step 1: Create Account', content)
        self.assertIn('Step 2: Download Miner', content)
        self.assertIn('Step 3: Start Earning', content)

    def test_social_share_tracking(self):
        response = self.client.post('/track_share', json={
            'user_id': 2,
            'platform': 'twitter',
            'share_url': 'https://twitter.com/intent/tweet?text=Mining%20RTC'
        })
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertTrue(result['tracked'])

    def test_user_progress_dashboard(self):
        response = self.client.get('/progress/1')
        self.assertEqual(response.status_code, 200)
        content = response.data.decode('utf-8')
        self.assertIn('45.75 RTC Earned', content)
        self.assertIn('2/3 Bounties Complete', content)
        self.assertIn('Next: Refer a Friend', content)

    def test_email_validation_during_registration(self):
        response = self.client.post('/register', data={
            'username': 'testuser',
            'email': 'invalid-email',
            'referral_code': ''
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Invalid email format', response.data)


if __name__ == '__main__':
    unittest.main()
