"""Tests for RustChain Agent Economy SDK"""

import pytest
from rustchain_agent import AgentClient, JobCategory
from rustchain_agent.models import (
    Job,
    JobCreate,
    JobClaim,
    JobDeliver,
    Reputation,
    MarketplaceStats,
)


class TestJobModels:
    """Test job data models."""
    
    def test_job_from_dict(self):
        """Test creating Job from dictionary."""
        data = {
            "id": "test-job-123",
            "poster_wallet": "poster-wallet",
            "title": "Test Job",
            "description": "A test job",
            "category": "code",
            "reward_rtc": 10.5,
            "tags": ["test", "python"],
            "status": "open",
        }
        job = Job.from_dict(data)
        assert job.id == "test-job-123"
        assert job.poster_wallet == "poster-wallet"
        assert job.title == "Test Job"
        assert job.reward_rtc == 10.5
        assert job.tags == ["test", "python"]
    
    def test_job_create_to_dict(self):
        """Test JobCreate serialization."""
        job = JobCreate(
            poster_wallet="my-wallet",
            title="Test Title",
            description="Test Description",
            category=JobCategory.CODE,
            reward_rtc=5.0,
            tags=["test"]
        )
        result = job.to_dict()
        assert result["poster_wallet"] == "my-wallet"
        assert result["category"] == "code"
        assert result["reward_rtc"] == 5.0
    
    def test_job_deliver_to_dict(self):
        """Test JobDeliver serialization."""
        delivery = JobDeliver(
            worker_wallet="worker",
            deliverable_url="https://example.com/output",
            result_summary="Completed work"
        )
        result = delivery.to_dict()
        assert result["worker_wallet"] == "worker"
        assert result["deliverable_url"] == "https://example.com/output"


class TestReputation:
    """Test reputation model."""
    
    def test_reputation_from_dict(self):
        """Test creating Reputation from dictionary."""
        data = {
            "wallet": "test-wallet",
            "trust_score": 95.5,
            "total_jobs_completed": 100,
            "total_jobs_disputed": 2,
            "total_earned_rtc": 500.0,
            "average_rating": 4.8,
        }
        rep = Reputation.from_dict(data)
        assert rep.wallet == "test-wallet"
        assert rep.trust_score == 95.5
        assert rep.total_jobs_completed == 100


class TestMarketplaceStats:
    """Test marketplace stats model."""
    
    def test_stats_from_dict(self):
        """Test creating MarketplaceStats from dictionary."""
        data = {
            "total_jobs": 500,
            "open_jobs": 50,
            "active_workers": 200,
            "total_volume_rtc": 10000.0,
            "platform_fee_rtc": 500.0,
            "average_reward_rtc": 25.0,
        }
        stats = MarketplaceStats.from_dict(data)
        assert stats.total_jobs == 500
        assert stats.open_jobs == 50
        assert stats.total_volume_rtc == 10000.0


class TestAgentClient:
    """Test AgentClient."""
    
    def test_client_initialization(self):
        """Test client can be initialized."""
        client = AgentClient()
        assert client.base_url == "https://rustchain.org"
        assert client.timeout == 30
    
    def test_custom_base_url(self):
        """Test client with custom base URL."""
        client = AgentClient(base_url="https://test.rustchain.org")
        assert client.base_url == "https://test.rustchain.org"


class TestJobCategory:
    """Test JobCategory enum."""
    
    def test_categories(self):
        """Test all job categories exist."""
        assert JobCategory.RESEARCH.value == "research"
        assert JobCategory.CODE.value == "code"
        assert JobCategory.VIDEO.value == "video"
        assert JobCategory.WRITING.value == "writing"
        assert JobCategory.OTHER.value == "other"
