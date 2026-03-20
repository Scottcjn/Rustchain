# SPDX-License-Identifier: MIT
import unittest
from unittest.mock import patch, MagicMock, mock_open
import sqlite3
import tempfile
import os
import json
import sys

# Add the root directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from bounty_bot_pro import BountyBotPRO
except ImportError:
    # Mock the class if not yet implemented
    class BountyBotPRO:
        def __init__(self, *args, **kwargs):
            pass

class TestBountyBotPRO(unittest.TestCase):

    def setUp(self):
        """Set up test database and bot instance"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name

        # Create test database schema
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS bounty_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wallet_address TEXT NOT NULL,
                    submission_url TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    ai_quality_score REAL DEFAULT 0.0,
                    technical_depth INTEGER DEFAULT 0,
                    clarity_score INTEGER DEFAULT 0,
                    originality_score INTEGER DEFAULT 0,
                    star_king_status TEXT DEFAULT 'none',
                    payout_amount REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS wallet_balances (
                    wallet_address TEXT PRIMARY KEY,
                    balance REAL NOT NULL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

        self.bot = BountyBotPRO(db_path=self.db_path, gemini_api_key="test_key")

    def tearDown(self):
        """Clean up test database"""
        os.unlink(self.db_path)

    @patch('requests.get')
    def test_verify_wallet_exists_valid(self, mock_get):
        """Test wallet verification with valid wallet"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'balance': 1500.75, 'status': 'active'}
        mock_get.return_value = mock_response

        result = self.bot.verify_wallet_exists('rust1test2wallet3address')

        self.assertTrue(result)
        mock_get.assert_called_once()

    @patch('requests.get')
    def test_verify_wallet_exists_invalid(self, mock_get):
        """Test wallet verification with invalid wallet"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = self.bot.verify_wallet_exists('invalid_wallet')

        self.assertFalse(result)

    @patch('requests.get')
    def test_query_wallet_balance(self, mock_get):
        """Test wallet balance querying"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'balance': 2500.0}
        mock_get.return_value = mock_response

        balance = self.bot.query_wallet_balance('rust1test2wallet3address')

        self.assertEqual(balance, 2500.0)

    @patch('requests.post')
    def test_ai_quality_scoring_high_quality(self, mock_post):
        """Test AI quality scoring for high-quality content"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'candidates': [{
                'content': {
                    'parts': [{
                        'text': '{"technical_depth": 9, "clarity": 8, "originality": 9, "overall_score": 8.7, "reasoning": "Excellent technical analysis of Rust blockchain consensus mechanisms."}'
                    }]
                }
            }]
        }
        mock_post.return_value = mock_response

        content = "Deep dive into Rust blockchain consensus algorithms and their performance implications..."
        scores = self.bot.evaluate_content_quality(content)

        self.assertEqual(scores['technical_depth'], 9)
        self.assertEqual(scores['clarity'], 8)
        self.assertEqual(scores['originality'], 9)
        self.assertAlmostEqual(scores['overall_score'], 8.7)

    @patch('requests.post')
    def test_ai_quality_scoring_low_quality(self, mock_post):
        """Test AI quality scoring for low-quality content"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'candidates': [{
                'content': {
                    'parts': [{
                        'text': '{"technical_depth": 2, "clarity": 3, "originality": 1, "overall_score": 2.0, "reasoning": "Very basic content with minimal technical insight."}'
                    }]
                }
            }]
        }
        mock_post.return_value = mock_response

        content = "Blockchain is good. Rust is fast. Here's a link: https://rust-lang.org"
        scores = self.bot.evaluate_content_quality(content)

        self.assertEqual(scores['technical_depth'], 2)
        self.assertEqual(scores['clarity'], 3)
        self.assertEqual(scores['originality'], 1)
        self.assertEqual(scores['overall_score'], 2.0)

    def test_star_king_detection_high_performer(self):
        """Test Star King detection for high-performing contributor"""
        # Insert test submissions for a wallet
        wallet_addr = 'rust1star2king3address'
        with sqlite3.connect(self.db_path) as conn:
            for i in range(5):
                conn.execute('''
                    INSERT INTO bounty_submissions
                    (wallet_address, submission_url, content_type, ai_quality_score, technical_depth, clarity_score, originality_score, payout_amount, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (wallet_addr, f'https://test.com/{i}', 'article', 8.5, 9, 8, 9, 250.0, 'approved'))

        star_status = self.bot.detect_star_king_status(wallet_addr)

        self.assertEqual(star_status, 'star_king')

    def test_star_king_detection_regular_contributor(self):
        """Test Star King detection for regular contributor"""
        wallet_addr = 'rust1regular2contributor'
        with sqlite3.connect(self.db_path) as conn:
            for i in range(3):
                conn.execute('''
                    INSERT INTO bounty_submissions
                    (wallet_address, submission_url, content_type, ai_quality_score, technical_depth, clarity_score, originality_score, payout_amount, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (wallet_addr, f'https://test.com/{i}', 'article', 6.0, 6, 6, 5, 150.0, 'approved'))

        star_status = self.bot.detect_star_king_status(wallet_addr)

        self.assertEqual(star_status, 'regular')

    def test_payout_calculation_star_king_bonus(self):
        """Test payout calculation with Star King bonus"""
        base_scores = {
            'technical_depth': 8,
            'clarity': 9,
            'originality': 8,
            'overall_score': 8.3
        }

        payout = self.bot.calculate_payout_amount(base_scores, star_king_status='star_king')

        # Base payout would be ~830 RTC, with 25% star king bonus = ~1037.5 RTC
        expected_payout = 830.0 * 1.25
        self.assertAlmostEqual(payout, expected_payout, places=1)

    def test_payout_calculation_regular_contributor(self):
        """Test payout calculation for regular contributor"""
        base_scores = {
            'technical_depth': 6,
            'clarity': 7,
            'originality': 5,
            'overall_score': 6.0
        }

        payout = self.bot.calculate_payout_amount(base_scores, star_king_status='regular')

        # Base payout would be ~600 RTC
        expected_payout = 600.0
        self.assertAlmostEqual(payout, expected_payout, places=1)

    def test_payout_calculation_minimum_threshold(self):
        """Test payout calculation below minimum threshold"""
        low_scores = {
            'technical_depth': 2,
            'clarity': 3,
            'originality': 1,
            'overall_score': 2.0
        }

        payout = self.bot.calculate_payout_amount(low_scores, star_king_status='none')

        # Should be 0 or very minimal for low quality
        self.assertLessEqual(payout, 50.0)

    @patch('requests.get')
    def test_content_extraction_from_url(self, mock_get):
        """Test content extraction from submission URL"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
            <body>
                <h1>Advanced Rust Blockchain Mining</h1>
                <p>This article explores the intricacies of Rust-based blockchain mining algorithms...</p>
                <p>Key technical innovations include optimized hash functions and memory management...</p>
            </body>
        </html>
        '''
        mock_get.return_value = mock_response

        content = self.bot.extract_content_from_url('https://example.com/rust-mining-guide')

        self.assertIn('Advanced Rust Blockchain Mining', content)
        self.assertIn('optimized hash functions', content)

    @patch.object(BountyBotPRO, 'verify_wallet_exists')
    @patch.object(BountyBotPRO, 'extract_content_from_url')
    @patch.object(BountyBotPRO, 'evaluate_content_quality')
    @patch.object(BountyBotPRO, 'detect_star_king_status')
    def test_process_submission_complete_workflow(self, mock_star_king, mock_quality, mock_extract, mock_wallet):
        """Test complete submission processing workflow"""
        # Setup mocks
        mock_wallet.return_value = True
        mock_extract.return_value = "High quality technical content about Rust blockchain development..."
        mock_quality.return_value = {
            'technical_depth': 8,
            'clarity': 9,
            'originality': 7,
            'overall_score': 8.0
        }
        mock_star_king.return_value = 'regular'

        # Process submission
        result = self.bot.process_submission(
            wallet_address='rust1test2wallet3address',
            submission_url='https://example.com/technical-article',
            content_type='article'
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['status'], 'approved')
        self.assertGreater(result['payout_amount'], 0)

        # Verify database entry
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT * FROM bounty_submissions
                WHERE wallet_address = ? AND submission_url = ?
            ''', ('rust1test2wallet3address', 'https://example.com/technical-article'))
            submission = cursor.fetchone()

            self.assertIsNotNone(submission)

    @patch.object(BountyBotPRO, 'verify_wallet_exists')
    def test_process_submission_invalid_wallet(self, mock_wallet):
        """Test submission processing with invalid wallet"""
        mock_wallet.return_value = False

        result = self.bot.process_submission(
            wallet_address='invalid_wallet',
            submission_url='https://example.com/article',
            content_type='article'
        )

        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Invalid wallet address')

    def test_database_integrity_constraints(self):
        """Test database maintains integrity with various edge cases"""
        # Test duplicate submission prevention
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO bounty_submissions
                (wallet_address, submission_url, content_type, status)
                VALUES (?, ?, ?, ?)
            ''', ('rust1test', 'https://example.com/duplicate', 'article', 'pending'))

            # Should handle duplicate gracefully
            try:
                conn.execute('''
                    INSERT INTO bounty_submissions
                    (wallet_address, submission_url, content_type, status)
                    VALUES (?, ?, ?, ?)
                ''', ('rust1test', 'https://example.com/duplicate', 'article', 'pending'))
            except sqlite3.IntegrityError:
                pass  # Expected for duplicate prevention

    def test_performance_metrics_tracking(self):
        """Test performance metrics are properly tracked"""
        # Insert various quality submissions
        test_data = [
            ('rust1user1', 8.5, 'star_king'),
            ('rust1user2', 6.0, 'regular'),
            ('rust1user3', 3.0, 'none'),
            ('rust1user4', 9.0, 'star_king')
        ]

        with sqlite3.connect(self.db_path) as conn:
            for wallet, score, status in test_data:
                conn.execute('''
                    INSERT INTO bounty_submissions
                    (wallet_address, submission_url, content_type, ai_quality_score, star_king_status, payout_amount, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (wallet, f'https://test.com/{wallet}', 'article', score, status, score * 100, 'approved'))

        metrics = self.bot.get_performance_metrics()

        self.assertGreater(metrics['total_submissions'], 0)
        self.assertIn('average_quality_score', metrics)
        self.assertIn('star_king_count', metrics)

if __name__ == '__main__':
    unittest.main()
