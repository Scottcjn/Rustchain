"""
Tests for RustChain Agent Economy SDK.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json

from rustchain_agent_sdk import AgentClient
from rustchain_agent_sdk.models import Job, Reputation, MarketStats
from rustchain_agent_sdk.exceptions import (
    AgentSDKError,
    AuthenticationError,
    InsufficientBalanceError,
    JobNotFoundError,
    InvalidParameterError,
    JobStateError
)


class TestAgentClient(unittest.TestCase):
    """Test cases for AgentClient."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = AgentClient(base_url="https://test.rustchain.org")
    
    @patch('rustchain_agent_sdk.client.urllib.request.urlopen')
    def test_post_job_success(self, mock_urlopen):
        """Test posting a job successfully."""
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "job_id": "test-job-123",
            "poster_wallet": "my-wallet",
            "title": "Test Job",
            "description": "Test description",
            "category": "code",
            "reward_rtc": 10.0,
            "status": "open"
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        job = self.client.post_job(
            poster_wallet="my-wallet",
            title="Test Job",
            description="Test description",
            category="code",
            reward_rtc=10.0
        )
        
        self.assertEqual(job.job_id, "test-job-123")
        self.assertEqual(job.title, "Test Job")
        self.assertEqual(job.status, "open")
    
    def test_post_job_invalid_category(self):
        """Test posting a job with invalid category."""
        with self.assertRaises(InvalidParameterError):
            self.client.post_job(
                poster_wallet="my-wallet",
                title="Test",
                description="Test",
                category="invalid_category",
                reward_rtc=10.0
            )
    
    def test_post_job_invalid_reward(self):
        """Test posting a job with invalid reward."""
        with self.assertRaises(InvalidParameterError):
            self.client.post_job(
                poster_wallet="my-wallet",
                title="Test",
                description="Test",
                reward_rtc=0.001  # Too low
            )
        
        with self.assertRaises(InvalidParameterError):
            self.client.post_job(
                poster_wallet="my-wallet",
                title="Test",
                description="Test",
                reward_rtc=10001  # Too high
            )
    
    @patch('rustchain_agent_sdk.client.urllib.request.urlopen')
    def test_list_jobs(self, mock_urlopen):
        """Test listing jobs."""
        mock_response = Mock()
        mock_response.read.return_value = json.dumps([
            {
                "job_id": "job-1",
                "title": "Job 1",
                "status": "open",
                "reward_rtc": 5.0,
                "poster_wallet": "wallet1"
            },
            {
                "job_id": "job-2", 
                "title": "Job 2",
                "status": "open",
                "reward_rtc": 10.0,
                "poster_wallet": "wallet2"
            }
        ]).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        jobs = self.client.list_jobs(category="code")
        
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].job_id, "job-1")
        self.assertEqual(jobs[1].job_id, "job-2")
    
    @patch('rustchain_agent_sdk.client.urllib.request.urlopen')
    def test_get_job(self, mock_urlopen):
        """Test getting job details."""
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "job_id": "test-job",
            "title": "Test Job",
            "description": "Test description",
            "status": "claimed",
            "reward_rtc": 15.0,
            "poster_wallet": "poster-wallet",
            "worker_wallet": "worker-wallet"
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        job = self.client.get_job("test-job")
        
        self.assertEqual(job.job_id, "test-job")
        self.assertEqual(job.status, "claimed")
        self.assertEqual(job.worker_wallet, "worker-wallet")
    
    @patch('rustchain_agent_sdk.client.urllib.request.urlopen')
    def test_claim_job(self, mock_urlopen):
        """Test claiming a job."""
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "job_id": "test-job",
            "status": "claimed",
            "worker_wallet": "worker-wallet"
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        job = self.client.claim_job("test-job", "worker-wallet")
        
        self.assertEqual(job.status, "claimed")
        self.assertEqual(job.worker_wallet, "worker-wallet")
    
    @patch('rustchain_agent_sdk.client.urllib_request.urlopen')
    def test_get_reputation(self, mock_urlopen):
        """Test getting reputation."""
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "wallet": "test-wallet",
            "trust_score": 95.5,
            "total_jobs": 100,
            "successful_jobs": 98,
            "failed_jobs": 2
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        rep = self.client.get_reputation("test-wallet")
        
        self.assertEqual(rep.wallet, "test-wallet")
        self.assertEqual(rep.trust_score, 95.5)
        self.assertEqual(rep.total_jobs, 100)
    
    @patch('rustchain_agent_sdk.client.urllib.request.urlopen')
    def test_get_stats(self, mock_urlopen):
        """Test getting market stats."""
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "total_jobs": 1000,
            "open_jobs": 50,
            "claimed_jobs": 30,
            "completed_jobs": 900,
            "total_volume_rtc": 5000.0,
            "average_reward": 5.0,
            "active_agents": 200
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        stats = self.client.get_stats()
        
        self.assertEqual(stats.total_jobs, 1000)
        self.assertEqual(stats.open_jobs, 50)
        self.assertEqual(stats.total_volume_rtc, 5000.0)


class TestJobModel(unittest.TestCase):
    """Test cases for Job model."""
    
    def test_job_from_dict(self):
        """Test creating Job from dictionary."""
        data = {
            "job_id": "test-123",
            "poster_wallet": "wallet1",
            "title": "Test Job",
            "description": "Description",
            "category": "code",
            "reward_rtc": 10.0,
            "status": "open",
            "tags": ["python", "api"]
        }
        
        job = Job.from_dict(data)
        
        self.assertEqual(job.job_id, "test-123")
        self.assertEqual(job.poster_wallet, "wallet1")
        self.assertEqual(job.title, "Test Job")
        self.assertEqual(job.category, "code")
        self.assertEqual(job.reward_rtc, 10.0)
        self.assertEqual(job.status, "open")
        self.assertEqual(job.tags, ["python", "api"])
    
    def test_job_to_dict(self):
        """Test converting Job to dictionary."""
        job = Job(
            job_id="test-123",
            poster_wallet="wallet1",
            title="Test Job",
            description="Description",
            category="code",
            reward_rtc=10.0,
            tags=["python"]
        )
        
        data = job.to_dict()
        
        self.assertEqual(data["job_id"], "test-123")
        self.assertEqual(data["poster_wallet"], "wallet1")
        self.assertEqual(data["title"], "Test Job")
        self.assertEqual(data["reward_rtc"], 10.0)


class TestReputationModel(unittest.TestCase):
    """Test cases for Reputation model."""
    
    def test_reputation_from_dict(self):
        """Test creating Reputation from dictionary."""
        data = {
            "wallet": "test-wallet",
            "trust_score": 90.0,
            "total_jobs": 50,
            "successful_jobs": 48,
            "failed_jobs": 2
        }
        
        rep = Reputation.from_dict(data)
        
        self.assertEqual(rep.wallet, "test-wallet")
        self.assertEqual(rep.trust_score, 90.0)
        self.assertEqual(rep.total_jobs, 50)
        self.assertEqual(rep.successful_jobs, 48)


class TestMarketStatsModel(unittest.TestCase):
    """Test cases for MarketStats model."""
    
    def test_market_stats_from_dict(self):
        """Test creating MarketStats from dictionary."""
        data = {
            "total_jobs": 1000,
            "open_jobs": 100,
            "claimed_jobs": 50,
            "completed_jobs": 850,
            "total_volume_rtc": 5000.0,
            "average_reward": 5.0,
            "active_agents": 150
        }
        
        stats = MarketStats.from_dict(data)
        
        self.assertEqual(stats.total_jobs, 1000)
        self.assertEqual(stats.open_jobs, 100)
        self.assertEqual(stats.total_volume_rtc, 5000.0)


if __name__ == '__main__':
    unittest.main()
