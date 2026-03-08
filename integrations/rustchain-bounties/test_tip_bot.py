#!/usr/bin/env python3
"""
Tests for RustChain GitHub Tip Bot
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tip_bot import TipBot, TipRecord, BountyState
from bounty_tracker import BountyTracker, Bounty


class TestTipBotParse:
    """Test tip command parsing"""
    
    def test_parse_simple_tip(self):
        bot = TipBot(github_token="dummy", payout_wallet="RTC123")
        
        result = bot.parse_tip_command("/tip @user 50 RTC")
        assert result == ("user", 50.0)
    
    def test_parse_tip_without_at(self):
        bot = TipBot(github_token="dummy", payout_wallet="RTC123")
        
        result = bot.parse_tip_command("/tip user 25 RTC")
        assert result == ("user", 25.0)
    
    def test_parse_tip_lowercase(self):
        bot = TipBot(github_token="dummy", payout_wallet="RTC123")
        
        result = bot.parse_tip_command("/tip @user 10 rtc")
        assert result == ("user", 10.0)
    
    def test_parse_tip_decimal(self):
        bot = TipBot(github_token="dummy", payout_wallet="RTC123")
        
        result = bot.parse_tip_command("/tip @user 15.5 RTC")
        assert result == ("user", 15.5)
    
    def test_parse_tip_with_claim(self):
        bot = TipBot(github_token="dummy", payout_wallet="RTC123")
        
        result = bot.parse_tip_command("/tip claim @user 100 RTC")
        assert result == ("user", 100.0)
    
    def test_parse_invalid_command(self):
        bot = TipBot(github_token="dummy", payout_wallet="RTC123")
        
        result = bot.parse_tip_command("Hello world")
        assert result is None
    
    def test_parse_tip_in_multiline(self):
        bot = TipBot(github_token="dummy", payout_wallet="RTC123")
        
        comment = """Thanks for the contribution!
/tip @contributor 75 RTC
Great work!"""
        
        result = bot.parse_tip_command(comment)
        assert result == ("contributor", 75.0)
    
    def test_parse_zero_amount(self):
        bot = TipBot(github_token="dummy", payout_wallet="RTC123")
        
        result = bot.parse_tip_command("/tip @user 0 RTC")
        assert result == ("user", 0.0)


class TestTipBotValidation:
    """Test tip validation logic"""
    
    @pytest.fixture
    def bot(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            state_file = f.name
        
        bot = TipBot(
            github_token="dummy",
            payout_wallet="RTC1d48d848a5aa5ecf2c5f01aa5fb64837daaf2f35",
            state_file=state_file,
            dry_run=True,
        )
        yield bot
        
        # Cleanup
        if os.path.exists(state_file):
            os.unlink(state_file)
    
    def test_validate_positive_amount(self, bot):
        # Should pass validation
        result = bot.parse_tip_command("/tip @user 50 RTC")
        assert result is not None
        assert result[1] > 0
    
    def test_reject_negative_amount(self, bot):
        # Negative amounts won't match regex, but test boundary
        result = bot.parse_tip_command("/tip @user -10 RTC")
        assert result is None
    
    def test_reject_excessive_amount(self, bot):
        """Amounts over 1000 should be rejected in processing"""
        result = bot.parse_tip_command("/tip @user 1500 RTC")
        assert result == ("user", 1500.0)
        # The actual rejection happens in process_tip, not parsing


class TestTipBotState:
    """Test state persistence"""
    
    def test_save_and_load_state(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            state_file = f.name
        
        try:
            bot = TipBot(
                github_token="dummy",
                payout_wallet="RTC123",
                state_file=state_file,
            )
            
            # Add a tip record
            tip = TipRecord(
                issue_number=1153,
                from_user="admin",
                to_user="contributor",
                amount_rtc=50.0,
                timestamp=datetime.now(timezone.utc).isoformat(),
                tx_hash="0xabc123",
                status="completed",
            )
            bot.state.tips.append(tip)
            bot.state.total_distributed = 50.0
            bot._save_state()
            
            # Load in new bot instance
            bot2 = TipBot(
                github_token="dummy",
                payout_wallet="RTC123",
                state_file=state_file,
            )
            
            assert len(bot2.state.tips) == 1
            assert bot2.state.total_distributed == 50.0
            assert bot2.state.tips[0].to_user == "contributor"
            
        finally:
            if os.path.exists(state_file):
                os.unlink(state_file)
    
    def test_empty_state(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            state_file = f.name
        
        try:
            bot = TipBot(
                github_token="dummy",
                payout_wallet="RTC123",
                state_file=state_file,
            )
            
            assert len(bot.state.tips) == 0
            assert bot.state.total_distributed == 0.0
            
        finally:
            if os.path.exists(state_file):
                os.unlink(state_file)


class TestTipBotMessages:
    """Test bot message generation"""
    
    def test_help_message(self):
        bot = TipBot(github_token="dummy", payout_wallet="RTC123")
        help_text = bot.get_help()
        
        assert "/tip" in help_text
        assert "RTC" in help_text
        assert "status" in help_text
    
    def test_status_message(self):
        bot = TipBot(github_token="dummy", payout_wallet="RTC123")
        status = bot.get_status("test/repo")
        
        assert "Tip Bot Status" in status
        assert "RTC" in status
    
    def test_status_with_tips(self):
        bot = TipBot(github_token="dummy", payout_wallet="RTC123")
        
        # Add some tips
        for i in range(3):
            tip = TipRecord(
                issue_number=100 + i,
                from_user="admin",
                to_user=f"user{i}",
                amount_rtc=10.0 * (i + 1),
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            bot.state.tips.append(tip)
            bot.state.total_distributed += tip.amount_rtc
        
        status = bot.get_status("test/repo")
        assert "**Total Tips:** 3" in status
        assert "60.00" in status  # 10 + 20 + 30


class TestBountyTracker:
    """Test bounty tracker functionality"""
    
    @pytest.fixture
    def tracker(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            state_file = f.name
        
        tr = BountyTracker(
            github_token="dummy",
            repo="test/repo",
            state_file=state_file,
        )
        yield tr
        
        if os.path.exists(state_file):
            os.unlink(state_file)
    
    def test_bounty_creation(self, tracker):
        bounty = Bounty(
            issue_number=1153,
            title="Test Bounty",
            description="Test description",
            reward_rtc=50.0,
        )
        
        tracker.bounties[1153] = bounty
        tracker._save_state()
        
        # Reload
        tracker2 = BountyTracker(
            github_token="dummy",
            repo="test/repo",
            state_file=tracker.state_file,
        )
        
        assert 1153 in tracker2.bounties
        assert tracker2.bounties[1153].title == "Test Bounty"
    
    def test_claim_bounty(self, tracker):
        bounty = Bounty(
            issue_number=1153,
            title="Test Bounty",
            description="Test",
            reward_rtc=50.0,
            status="open",
        )
        tracker.bounties[1153] = bounty
        
        result = tracker.claim_bounty(1153, "contributor", "https://github.com/pr/1")
        
        assert result is not None
        assert result.status == "claimed"
        assert result.claimant == "contributor"
    
    def test_mark_paid(self, tracker):
        bounty = Bounty(
            issue_number=1153,
            title="Test Bounty",
            description="Test",
            reward_rtc=50.0,
            status="completed",
            claimant="contributor",
        )
        tracker.bounties[1153] = bounty
        
        result = tracker.mark_paid(1153)
        
        assert result is not None
        assert result.status == "paid"
        assert result.paid_at is not None
    
    def test_get_summary(self, tracker):
        # Add bounties in different states
        for i, status in enumerate(["open", "claimed", "completed", "paid"]):
            bounty = Bounty(
                issue_number=100 + i,
                title=f"Bounty {i}",
                description="Test",
                reward_rtc=25.0,
                status=status,
            )
            tracker.bounties[100 + i] = bounty
        
        summary = tracker.get_summary()
        
        assert "**Total Bounties:** 4" in summary
        assert "**Open:** 1" in summary
        assert "**Claimed:** 1" in summary
        assert "**Completed:** 1" in summary
        assert "**Paid:** 1" in summary


class TestWebhookSignature:
    """Test webhook signature verification"""
    
    def test_valid_signature(self):
        bot = TipBot(github_token="dummy", payout_wallet="RTC123")
        
        payload = b'{"action": "created"}'
        secret = "test-secret"
        
        import hmac
        import hashlib
        
        expected_sig = "sha256=" + hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        assert bot.verify_webhook_signature(payload, expected_sig, secret) is True
    
    def test_invalid_signature(self):
        bot = TipBot(github_token="dummy", payout_wallet="RTC123")
        
        payload = b'{"action": "created"}'
        
        assert bot.verify_webhook_signature(payload, "sha256=invalid", "secret") is False
    
    def test_missing_signature(self):
        bot = TipBot(github_token="dummy", payout_wallet="RTC123")
        
        assert bot.verify_webhook_signature(b"{}", "", "secret") is False


class TestTXHashGeneration:
    """Test transaction hash generation"""
    
    def test_deterministic_hash(self):
        bot = TipBot(github_token="dummy", payout_wallet="RTC123")
        
        hash1 = bot.generate_tx_hash(1153, "user", 50.0)
        hash2 = bot.generate_tx_hash(1153, "user", 50.0)
        
        assert hash1 == hash2
        assert hash1.startswith("0x")
        assert len(hash1) == 42  # 0x + 40 hex chars
    
    def test_unique_hashes(self):
        bot = TipBot(github_token="dummy", payout_wallet="RTC123")
        
        hash1 = bot.generate_tx_hash(1153, "user1", 50.0)
        hash2 = bot.generate_tx_hash(1153, "user2", 50.0)
        
        assert hash1 != hash2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
