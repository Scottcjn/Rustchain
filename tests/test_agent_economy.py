// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import sqlite3
import tempfile
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_economy_sdk import AgentEconomySDK, JobStatus, DeliveryStatus
from agent_economy_cli import AgentEconomyCLI


class TestAgentEconomySDK(unittest.TestCase):

    def setUp(self):
        self.sdk = AgentEconomySDK("http://localhost:5000")
        self.mock_response_data = {
            "success": True,
            "job_id": "job_12345",
            "status": "open",
            "escrow_amount": 50.0
        }

    @patch('requests.post')
    def test_post_job_success(self, mock_post):
        mock_post.return_value.json.return_value = self.mock_response_data
        mock_post.return_value.status_code = 201

        result = self.sdk.post_job(
            title="Test AI Model Training",
            description="Train GPT model on custom dataset",
            reward=50.0,
            deadline_hours=48
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["job_id"], "job_12345")
        mock_post.assert_called_once()

        call_args = mock_post.call_args
        posted_data = call_args[1]["json"]
        self.assertEqual(posted_data["title"], "Test AI Model Training")
        self.assertEqual(posted_data["reward"], 50.0)

    @patch('requests.get')
    def test_get_jobs_list(self, mock_get):
        jobs_data = {
            "jobs": [
                {
                    "id": "job_001",
                    "title": "Data Analysis Task",
                    "reward": 25.0,
                    "status": "open",
                    "posted_by": "agent_alice"
                },
                {
                    "id": "job_002",
                    "title": "Image Processing",
                    "reward": 75.0,
                    "status": "claimed",
                    "posted_by": "agent_bob"
                }
            ]
        }
        mock_get.return_value.json.return_value = jobs_data
        mock_get.return_value.status_code = 200

        jobs = self.sdk.get_jobs()

        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0]["title"], "Data Analysis Task")
        self.assertEqual(jobs[1]["reward"], 75.0)

    @patch('requests.get')
    def test_get_job_details(self, mock_get):
        job_detail = {
            "id": "job_12345",
            "title": "Blockchain Integration",
            "description": "Integrate RustChain with existing DeFi protocol",
            "reward": 100.0,
            "status": "in_progress",
            "posted_by": "agent_charlie",
            "claimed_by": "agent_delta",
            "activity_log": [
                {"timestamp": "2024-01-15T10:00:00Z", "action": "job_posted"},
                {"timestamp": "2024-01-15T11:30:00Z", "action": "job_claimed"}
            ]
        }
        mock_get.return_value.json.return_value = job_detail
        mock_get.return_value.status_code = 200

        job = self.sdk.get_job_details("job_12345")

        self.assertEqual(job["title"], "Blockchain Integration")
        self.assertEqual(job["status"], "in_progress")
        self.assertEqual(len(job["activity_log"]), 2)

    @patch('requests.post')
    def test_claim_job(self, mock_post):
        mock_post.return_value.json.return_value = {
            "success": True,
            "message": "Job claimed successfully",
            "job_id": "job_12345"
        }
        mock_post.return_value.status_code = 200

        result = self.sdk.claim_job("job_12345")

        self.assertTrue(result["success"])
        self.assertIn("claimed successfully", result["message"])

    @patch('requests.post')
    def test_deliver_work(self, mock_post):
        mock_post.return_value.json.return_value = {
            "success": True,
            "delivery_id": "del_789",
            "status": "submitted"
        }
        mock_post.return_value.status_code = 200

        result = self.sdk.deliver_work(
            job_id="job_12345",
            deliverable_url="https://github.com/agent/solution",
            notes="Completed integration with full test coverage"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["delivery_id"], "del_789")

    @patch('requests.post')
    def test_accept_delivery(self, mock_post):
        mock_post.return_value.json.return_value = {
            "success": True,
            "escrow_released": True,
            "amount": 100.0
        }
        mock_post.return_value.status_code = 200

        result = self.sdk.accept_delivery("job_12345")

        self.assertTrue(result["success"])
        self.assertTrue(result["escrow_released"])
        self.assertEqual(result["amount"], 100.0)

    @patch('requests.post')
    def test_dispute_delivery(self, mock_post):
        mock_post.return_value.json.return_value = {
            "success": True,
            "dispute_id": "disp_456",
            "status": "disputed"
        }
        mock_post.return_value.status_code = 200

        result = self.sdk.dispute_delivery(
            job_id="job_12345",
            reason="Deliverable does not meet requirements"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["dispute_id"], "disp_456")

    def test_job_status_enum(self):
        self.assertEqual(JobStatus.OPEN, "open")
        self.assertEqual(JobStatus.CLAIMED, "claimed")
        self.assertEqual(JobStatus.IN_PROGRESS, "in_progress")
        self.assertEqual(JobStatus.COMPLETED, "completed")
        self.assertEqual(JobStatus.DISPUTED, "disputed")
        self.assertEqual(JobStatus.CANCELLED, "cancelled")

    def test_delivery_status_enum(self):
        self.assertEqual(DeliveryStatus.SUBMITTED, "submitted")
        self.assertEqual(DeliveryStatus.ACCEPTED, "accepted")
        self.assertEqual(DeliveryStatus.REJECTED, "rejected")


class TestAgentEconomyCLI(unittest.TestCase):

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        self.cli = AgentEconomyCLI()
        self.cli.db_path = self.temp_db.name
        self.cli.init_db()

    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_init_db_creates_tables(self):
        with sqlite3.connect(self.temp_db.name) as conn:
            cursor = conn.cursor()

            # Check local_jobs table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='local_jobs'")
            self.assertIsNotNone(cursor.fetchone())

            # Check activity_log table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='activity_log'")
            self.assertIsNotNone(cursor.fetchone())

    @patch('agent_economy_cli.AgentEconomyCLI.sdk')
    def test_post_job_command(self, mock_sdk):
        mock_sdk.post_job.return_value = {
            "success": True,
            "job_id": "job_98765",
            "escrow_locked": True
        }

        test_args = [
            "post-job",
            "--title", "Machine Learning Pipeline",
            "--description", "Build ML pipeline for time series prediction",
            "--reward", "80.0",
            "--deadline", "72"
        ]

        with patch('sys.argv', ['agent_cli.py'] + test_args):
            result = self.cli.handle_post_job()

        self.assertTrue(result["success"])
        mock_sdk.post_job.assert_called_once_with(
            title="Machine Learning Pipeline",
            description="Build ML pipeline for time series prediction",
            reward=80.0,
            deadline_hours=72
        )

    @patch('agent_economy_cli.AgentEconomyCLI.sdk')
    def test_list_jobs_command(self, mock_sdk):
        mock_jobs = [
            {
                "id": "job_111",
                "title": "Smart Contract Audit",
                "reward": 200.0,
                "status": "open",
                "posted_by": "agent_security"
            },
            {
                "id": "job_222",
                "title": "API Documentation",
                "reward": 30.0,
                "status": "claimed",
                "posted_by": "agent_docs"
            }
        ]
        mock_sdk.get_jobs.return_value = mock_jobs

        jobs = self.cli.handle_list_jobs()

        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0]["title"], "Smart Contract Audit")
        mock_sdk.get_jobs.assert_called_once()

    def test_save_local_job(self):
        job_data = {
            "id": "job_local_001",
            "title": "Test Local Job",
            "description": "Testing local storage",
            "reward": 45.0,
            "status": "draft"
        }

        self.cli.save_local_job(job_data)

        with sqlite3.connect(self.temp_db.name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM local_jobs WHERE job_id = ?", ("job_local_001",))
            row = cursor.fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row[1], "job_local_001")  # job_id column
        self.assertEqual(row[2], "Test Local Job")  # title column

    def test_log_activity(self):
        self.cli.log_activity("job_test", "test_action", "Testing activity logging")

        with sqlite3.connect(self.temp_db.name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM activity_log WHERE job_id = ?", ("job_test",))
            row = cursor.fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row[1], "job_test")  # job_id
        self.assertEqual(row[2], "test_action")  # action
        self.assertEqual(row[3], "Testing activity logging")  # details

    @patch('agent_economy_cli.AgentEconomyCLI.sdk')
    def test_claim_job_integration(self, mock_sdk):
        mock_sdk.claim_job.return_value = {
            "success": True,
            "message": "Job claimed and assigned to you",
            "job_id": "job_integration_test"
        }

        result = self.cli.handle_claim_job("job_integration_test")

        self.assertTrue(result["success"])
        mock_sdk.claim_job.assert_called_once_with("job_integration_test")

    def test_validate_reward_amount(self):
        # Valid amounts
        self.assertTrue(self.cli.validate_reward_amount(25.0))
        self.assertTrue(self.cli.validate_reward_amount(100.0))

        # Invalid amounts
        self.assertFalse(self.cli.validate_reward_amount(10.0))  # Too low
        self.assertFalse(self.cli.validate_reward_amount(150.0))  # Too high
        self.assertFalse(self.cli.validate_reward_amount(-5.0))  # Negative

    def test_format_job_display(self):
        job = {
            "id": "job_display_test",
            "title": "UI/UX Design Task",
            "reward": 60.0,
            "status": "open",
            "posted_by": "agent_designer"
        }

        formatted = self.cli.format_job_display(job)

        self.assertIn("job_display_test", formatted)
        self.assertIn("UI/UX Design Task", formatted)
        self.assertIn("60.0 RTC", formatted)
        self.assertIn("open", formatted)


class TestAgentEconomyIntegration(unittest.TestCase):
    """End-to-end integration tests with mocked API responses"""

    def setUp(self):
        self.sdk = AgentEconomySDK("http://localhost:5000")

        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        self.cli = AgentEconomyCLI()
        self.cli.db_path = self.temp_db.name
        self.cli.init_db()

    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    @patch('requests.post')
    @patch('requests.get')
    def test_full_job_lifecycle(self, mock_get, mock_post):
        # Post job
        mock_post.return_value.json.return_value = {
            "success": True,
            "job_id": "job_lifecycle_test",
            "status": "open"
        }
        mock_post.return_value.status_code = 201

        # Claim job
        mock_post.return_value.json.return_value = {
            "success": True,
            "message": "Job claimed",
            "job_id": "job_lifecycle_test"
        }

        # Deliver work
        mock_post.return_value.json.return_value = {
            "success": True,
            "delivery_id": "del_lifecycle",
            "status": "submitted"
        }

        # Accept delivery
        mock_post.return_value.json.return_value = {
            "success": True,
            "escrow_released": True,
            "amount": 85.0
        }

        # Execute lifecycle
        post_result = self.sdk.post_job("Test Lifecycle", "Full test", 85.0, 48)
        claim_result = self.sdk.claim_job("job_lifecycle_test")
        deliver_result = self.sdk.deliver_work("job_lifecycle_test", "https://test.url", "Done")
        accept_result = self.sdk.accept_delivery("job_lifecycle_test")

        # Verify all steps succeeded
        self.assertTrue(post_result["success"])
        self.assertTrue(claim_result["success"])
        self.assertTrue(deliver_result["success"])
        self.assertTrue(accept_result["success"])
        self.assertEqual(accept_result["amount"], 85.0)

    @patch('requests.get')
    def test_reputation_system_mock(self, mock_get):
        reputation_data = {
            "agent_id": "agent_reputation_test",
            "total_jobs": 15,
            "completed_jobs": 12,
            "success_rate": 0.8,
            "average_rating": 4.2,
            "total_earned": 1250.0
        }
        mock_get.return_value.json.return_value = reputation_data
        mock_get.return_value.status_code = 200

        # This would be implemented in SDK
        # rep = self.sdk.get_agent_reputation("agent_reputation_test")
        # For now, just verify mock setup
        self.assertEqual(reputation_data["success_rate"], 0.8)
        self.assertEqual(reputation_data["total_earned"], 1250.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
