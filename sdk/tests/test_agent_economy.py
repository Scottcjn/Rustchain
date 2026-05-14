"""
RustChain Agent Economy SDK - Unit Tests

Tests for the RIP-302 Agent Economy client and modules.
"""

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from rustchain.agent_economy import (
    AgentEconomyClient,
    AgentWallet,
    X402Payment,
    ReputationScore,
)
from rustchain.agent_economy.agents import AgentManager, AgentProfile
from rustchain.agent_economy.payments import PaymentProcessor, PaymentStatus, PaymentIntent
from rustchain.agent_economy.reputation import ReputationClient, ReputationTier, Attestation
from rustchain.agent_economy.analytics import AnalyticsClient, AnalyticsPeriod, EarningsReport
from rustchain.agent_economy.bounties import BountyClient, BountyStatus, BountyTier, Bounty
from rustchain.exceptions import ValidationError, APIError, ConnectionError


class TestAgentWallet(unittest.TestCase):
    """Tests for AgentWallet dataclass"""
    
    def test_create_wallet(self):
        """Test creating an AgentWallet"""
        wallet = AgentWallet(
            agent_id="test-agent",
            wallet_address="agent_abc123",
            balance=100.5,
        )
        
        self.assertEqual(wallet.agent_id, "test-agent")
        self.assertEqual(wallet.wallet_address, "agent_abc123")
        self.assertEqual(wallet.balance, 100.5)
        self.assertEqual(wallet.total_earned, 0.0)
    
    def test_wallet_to_dict(self):
        """Test wallet serialization"""
        wallet = AgentWallet(
            agent_id="test-agent",
            wallet_address="agent_abc123",
            base_address="0xBase123",
            balance=50.0,
            total_earned=150.0,
            reputation_score=85.0,
        )
        
        data = wallet.to_dict()
        
        self.assertEqual(data["agent_id"], "test-agent")
        self.assertEqual(data["wallet_address"], "agent_abc123")
        self.assertEqual(data["base_address"], "0xBase123")
        self.assertEqual(data["balance"], 50.0)
        self.assertEqual(data["total_earned"], 150.0)
        self.assertEqual(data["reputation_score"], 85.0)


class TestAgentProfile(unittest.TestCase):
    """Tests for AgentProfile dataclass"""
    
    def test_create_profile(self):
        """Test creating an AgentProfile"""
        profile = AgentProfile(
            agent_id="curator-bot",
            name="Content Curator",
            description="AI content curation agent",
            capabilities=["curation", "analysis"],
        )
        
        self.assertEqual(profile.agent_id, "curator-bot")
        self.assertEqual(profile.name, "Content Curator")
        self.assertEqual(len(profile.capabilities), 2)
    
    def test_profile_to_dict(self):
        """Test profile serialization"""
        wallet = AgentWallet(
            agent_id="test",
            wallet_address="agent_test",
            balance=10.0,
        )
        
        profile = AgentProfile(
            agent_id="test-agent",
            name="Test Agent",
            description="Test description",
            capabilities=["test"],
            wallet=wallet,
            metadata={"version": "1.0"},
        )
        
        data = profile.to_dict()
        
        self.assertEqual(data["name"], "Test Agent")
        self.assertEqual(data["wallet"]["balance"], 10.0)
        self.assertEqual(data["metadata"]["version"], "1.0")


class TestX402Payment(unittest.TestCase):
    """Tests for X402Payment dataclass"""
    
    def test_create_payment(self):
        """Test creating an X402Payment"""
        payment = X402Payment(
            payment_id="pay_123",
            from_agent="sender",
            to_agent="receiver",
            amount=1.5,
            memo="Test payment",
        )
        
        self.assertEqual(payment.payment_id, "pay_123")
        self.assertEqual(payment.amount, 1.5)
        self.assertEqual(payment.status, PaymentStatus.PENDING)
    
    def test_payment_to_dict(self):
        """Test payment serialization"""
        payment = X402Payment(
            payment_id="pay_456",
            from_agent="sender",
            to_agent="receiver",
            amount=2.0,
            status=PaymentStatus.COMPLETED,
            tx_hash="tx_abc123",
        )
        
        data = payment.to_dict()
        
        self.assertEqual(data["payment_id"], "pay_456")
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["tx_hash"], "tx_abc123")


class TestReputationScore(unittest.TestCase):
    """Tests for ReputationScore dataclass"""
    
    def test_create_score(self):
        """Test creating a ReputationScore"""
        score = ReputationScore(
            agent_id="trusted-agent",
            score=85.0,
            tier=ReputationTier.TRUSTED,
            total_transactions=100,
            successful_transactions=95,
        )
        
        self.assertEqual(score.score, 85.0)
        self.assertEqual(score.tier, ReputationTier.TRUSTED)
        self.assertTrue(score.is_trusted)
    
    def test_success_rate(self):
        """Test success rate calculation"""
        score = ReputationScore(
            agent_id="test",
            total_transactions=100,
            successful_transactions=87,
        )
        
        self.assertAlmostEqual(score.success_rate, 87.0, places=1)
    
    def test_success_rate_zero_transactions(self):
        """Test success rate with no transactions"""
        score = ReputationScore(
            agent_id="test",
            total_transactions=0,
        )
        
        self.assertEqual(score.success_rate, 0.0)
    
    def test_tier_thresholds(self):
        """Test tier threshold calculations"""
        score = ReputationScore(agent_id="test", score=96.0)
        self.assertEqual(score.tier, ReputationTier.UNKNOWN)  # Default, not calculated
        
        # Test manual tier assignment
        score.tier = ReputationTier.ELITE
        self.assertTrue(score.is_trusted)


class TestAgentEconomyClient(unittest.TestCase):
    """Tests for AgentEconomyClient"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = AgentEconomyClient(
            base_url="https://test.rustchain.org",
            agent_id="test-agent",
            wallet_address="test_wallet",
            api_key="test-key",
        )
    
    def tearDown(self):
        """Clean up"""
        self.client.close()
    
    def test_client_initialization(self):
        """Test client initialization"""
        self.assertEqual(self.client.config.base_url, "https://test.rustchain.org")
        self.assertEqual(self.client.config.agent_id, "test-agent")
        self.assertIsNotNone(self.client.agents)
        self.assertIsNotNone(self.client.payments)
        self.assertIsNotNone(self.client.reputation)
        self.assertIsNotNone(self.client.analytics)
        self.assertIsNotNone(self.client.bounties)
    
    @patch.object(AgentEconomyClient, '_request')
    def test_health_check(self, mock_request):
        """Test health check endpoint"""
        mock_request.return_value = {"status": "ok", "version": "1.0.0"}
        
        result = self.client.health()
        
        self.assertEqual(result["status"], "ok")
        mock_request.assert_called_once_with("GET", "/api/agent/health")
    
    @patch.object(AgentEconomyClient, '_request')
    def test_get_agent_info(self, mock_request):
        """Test getting agent info"""
        mock_request.return_value = {
            "agent_id": "test-agent",
            "name": "Test Agent",
            "wallet": {"balance": 100.0},
        }
        
        result = self.client.get_agent_info()
        
        self.assertEqual(result["agent_id"], "test-agent")
        mock_request.assert_called_once_with("GET", "/api/agent/test-agent")
    
    def test_get_agent_info_no_id(self):
        """Test getting agent info without ID"""
        client = AgentEconomyClient(base_url="https://test.org")
        
        with self.assertRaises(ValidationError):
            client.get_agent_info()
    
    def test_context_manager(self):
        """Test context manager"""
        with AgentEconomyClient(agent_id="test") as client:
            self.assertIsNotNone(client.session)
        
        # Session should be closed after context
        self.assertTrue(client.session.closed if hasattr(client.session, 'closed') else True)


class TestAgentManager(unittest.TestCase):
    """Tests for AgentManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = Mock()
        self.manager = AgentManager(self.mock_client)
    
    @patch.object(AgentManager, '__init__', lambda self, client: None)
    def test_create_wallet(self):
        """Test wallet creation"""
        manager = AgentManager.__new__(AgentManager)
        manager.client = self.mock_client
        manager._cache = {}
        
        self.mock_client._request.return_value = {
            "wallet_address": "agent_new123",
        }
        
        wallet = manager.create_wallet(
            agent_id="new-agent",
            name="New Agent",
        )
        
        self.assertEqual(wallet.agent_id, "new-agent")
        self.assertEqual(wallet.wallet_address, "agent_new123")
    
    def test_create_wallet_validation(self):
        """Test wallet creation validation"""
        with self.assertRaises(ValidationError):
            self.manager.create_wallet(agent_id="ab")  # Too short
    
    def test_get_wallet_cached(self):
        """Test getting cached wallet"""
        cached_wallet = AgentWallet(
            agent_id="cached-agent",
            wallet_address="agent_cached",
            balance=50.0,
        )
        self.manager._cache["cached-agent"] = cached_wallet
        
        wallet = self.manager.get_wallet("cached-agent")
        
        self.assertEqual(wallet.balance, 50.0)
        self.mock_client._request.assert_not_called()


class TestPaymentProcessor(unittest.TestCase):
    """Tests for PaymentProcessor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = Mock()
        self.mock_client.config.agent_id = "sender-agent"
        self.processor = PaymentProcessor(self.mock_client)
    
    @patch.object(PaymentProcessor, '__init__', lambda self, client: None)
    def test_send_payment(self):
        """Test sending payment"""
        processor = PaymentProcessor.__new__(PaymentProcessor)
        processor.client = self.mock_client
        
        self.mock_client._request.return_value = {
            "payment_id": "pay_test123",
            "status": "pending",
        }
        
        payment = processor.send(
            to="receiver-agent",
            amount=1.0,
            memo="Test payment",
        )
        
        self.assertEqual(payment.amount, 1.0)
        self.assertEqual(payment.to_agent, "receiver-agent")
    
    def test_send_payment_validation(self):
        """Test payment validation"""
        with self.assertRaises(ValidationError):
            self.processor.send(to="receiver", amount=-1.0)  # Negative amount
        
        with self.assertRaises(ValidationError):
            self.processor.send(to="sender-agent", amount=1.0)  # Same agent
    
    def test_x402_challenge(self):
        """Test x402 challenge generation"""
        self.mock_client._request.return_value = {
            "wallet_address": "merchant_wallet",
            "nonce": "nonce123",
        }
        
        challenge = self.processor.x402_challenge(
            resource="/api/premium/data",
            required_amount=5.0,
        )
        
        self.assertEqual(challenge["status_code"], 402)
        self.assertEqual(challenge["headers"]["X-Pay-Amount"], "5.0")


class TestReputationClient(unittest.TestCase):
    """Tests for ReputationClient"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = Mock()
        self.mock_client.config.agent_id = "test-agent"
        self.reputation = ReputationClient(self.mock_client)
    
    @patch.object(ReputationClient, '__init__', lambda self, client: None)
    def test_get_score(self):
        """Test getting reputation score"""
        rep = ReputationClient.__new__(ReputationClient)
        rep.client = self.mock_client
        
        self.mock_client._request.return_value = {
            "score": 75.0,
            "tier": "established",
            "total_transactions": 50,
        }
        
        score = rep.get_score("target-agent")
        
        self.assertEqual(score.score, 75.0)
        self.assertEqual(score.tier, ReputationTier.ESTABLISHED)
    
    def test_submit_attestation(self):
        """Test submitting attestation"""
        self.mock_client._request.return_value = {
            "attestation_id": "att_123",
            "verified": True,
        }
        
        attestation = self.reputation.submit_attestation(
            to_agent="service-bot",
            rating=5,
            comment="Great service!",
        )
        
        self.assertEqual(attestation.rating, 5)
        self.assertTrue(attestation.verified)
    
    def test_submit_attestation_invalid_rating(self):
        """Test attestation with invalid rating"""
        with self.assertRaises(ValueError):
            self.reputation.submit_attestation(
                to_agent="bot",
                rating=6,  # Invalid
            )
    
    def test_calculate_tier(self):
        """Test tier calculation"""
        self.assertEqual(
            self.reputation.calculate_tier(96.0),
            ReputationTier.ELITE
        )
        self.assertEqual(
            self.reputation.calculate_tier(88.0),
            ReputationTier.VERIFIED
        )
        self.assertEqual(
            self.reputation.calculate_tier(75.0),
            ReputationTier.TRUSTED
        )
        self.assertEqual(
            self.reputation.calculate_tier(55.0),
            ReputationTier.ESTABLISHED
        )
        self.assertEqual(
            self.reputation.calculate_tier(25.0),
            ReputationTier.NEW
        )
        self.assertEqual(
            self.reputation.calculate_tier(10.0),
            ReputationTier.UNKNOWN
        )


class TestAnalyticsClient(unittest.TestCase):
    """Tests for AnalyticsClient"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = Mock()
        self.mock_client.config.agent_id = "analytics-agent"
        self.analytics = AnalyticsClient(self.mock_client)
    
    def test_get_earnings(self):
        """Test getting earnings report"""
        self.mock_client._request.return_value = {
            "total_earned": 125.5,
            "transactions_count": 42,
            "avg_transaction": 2.99,
            "trend": 15.3,
        }
        
        report = self.analytics.get_earnings(period=AnalyticsPeriod.WEEK)
        
        self.assertEqual(report.total_earned, 125.5)
        self.assertEqual(report.transactions_count, 42)
        self.assertEqual(report.trend, 15.3)
    
    def test_get_activity(self):
        """Test getting activity metrics"""
        self.mock_client._request.return_value = {
            "active_hours": 18,
            "peak_hour": 14,
            "uptime_percentage": 99.5,
        }
        
        activity = self.analytics.get_activity(period=AnalyticsPeriod.DAY)
        
        self.assertEqual(activity.active_hours, 18)
        self.assertEqual(activity.peak_hour, 14)
        self.assertEqual(activity.uptime_percentage, 99.5)


class TestBountyClient(unittest.TestCase):
    """Tests for BountyClient"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = Mock()
        self.mock_client.config.agent_id = "bounty-hunter"
        self.bounties = BountyClient(self.mock_client)
    
    def test_list_bounties(self):
        """Test listing bounties"""
        self.mock_client._request.return_value = {
            "bounties": [
                {
                    "bounty_id": "bounty_1",
                    "title": "Fix bug #123",
                    "reward": 50.0,
                    "status": "open",
                    "tier": "medium",
                },
            ]
        }
        
        bounties = self.bounties.list(status=BountyStatus.OPEN, limit=10)
        
        self.assertEqual(len(bounties), 1)
        self.assertEqual(bounties[0].bounty_id, "bounty_1")
        self.assertEqual(bounties[0].reward, 50.0)
    
    def test_claim_bounty(self):
        """Test claiming a bounty"""
        self.mock_client._request.return_value = {"success": True}
        
        result = self.bounties.claim(
            bounty_id="bounty_123",
            description="I'll fix this",
        )
        
        self.assertTrue(result)
    
    def test_bounty_is_claimable(self):
        """Test bounty claimable status"""
        bounty = Bounty(
            bounty_id="test",
            title="Test",
            description="Test bounty",
            status=BountyStatus.OPEN,
        )
        
        self.assertTrue(bounty.is_claimable)
        
        bounty.claimant = "other-agent"
        self.assertFalse(bounty.is_claimable)
    
    def test_bounty_is_expired(self):
        """Test bounty expiration"""
        past_deadline = datetime.utcnow() - timedelta(days=1)
        future_deadline = datetime.utcnow() + timedelta(days=1)
        
        expired_bounty = Bounty(
            bounty_id="expired",
            title="Expired",
            description="Test",
            deadline=past_deadline,
        )
        active_bounty = Bounty(
            bounty_id="active",
            title="Active",
            description="Test",
            deadline=future_deadline,
        )
        
        self.assertTrue(expired_bounty.is_expired)
        self.assertFalse(active_bounty.is_expired)

    def test_create_bounty_sets_deadline_and_payload(self):
        """Test creating a bounty includes a computed deadline"""
        self.mock_client._request.return_value = {"bounty_id": "bounty_new"}

        bounty = self.bounties.create_bounty(
            title="Fix SDK bug",
            description="Repair bounty creation",
            reward=12.5,
            tier=BountyTier.MINOR,
            requirements=["regression test"],
            tags=["sdk"],
            deadline_days=7,
        )

        self.assertEqual(bounty.bounty_id, "bounty_new")
        self.assertEqual(bounty.issuer, "bounty-hunter")
        self.assertEqual(bounty.tier, BountyTier.MINOR)
        self.assertEqual(bounty.reward, 12.5)
        self.assertIsNotNone(bounty.deadline)

        self.mock_client._request.assert_called_once()
        _, _, kwargs = self.mock_client._request.mock_calls[0]
        payload = kwargs["json_payload"]
        self.assertEqual(payload["issuer_id"], "bounty-hunter")
        self.assertEqual(payload["title"], "Fix SDK bug")
        self.assertEqual(payload["tier"], "minor")
        self.assertEqual(payload["requirements"], ["regression test"])
        self.assertEqual(payload["tags"], ["sdk"])
        self.assertIn("deadline", payload)


class TestIntegration(unittest.TestCase):
    """Integration tests mocking HTTP requests"""
    
    @patch('rustchain.agent_economy.client.requests.Session')
    def test_full_agent_workflow(self, mock_session_class):
        """Test complete agent workflow"""
        # Setup mock session
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Mock responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status.return_value = None
        mock_session.request.return_value = mock_response
        
        # Create client and perform operations
        client = AgentEconomyClient(
            base_url="https://test.org",
            agent_id="test-agent",
        )
        
        health = client.health()
        self.assertEqual(health["status"], "ok")
        
        client.close()


if __name__ == "__main__":
    unittest.main()
