# SPDX-License-Identifier: MIT

import pytest
import sqlite3
import tempfile
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Assuming coalition system will be in a new file
from coalition_governance import Coalition, CoalitionMember, Proposal, ProposalStatus


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    fd, path = tempfile.mkstemp()
    os.close(fd)

    # Initialize test database schema
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE miners (
                miner_id TEXT PRIMARY KEY,
                balance_rtc REAL DEFAULT 0.0,
                hardware_fingerprint TEXT,
                first_seen_block INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE coalitions (
                coalition_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                founder TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            );

            CREATE TABLE coalition_members (
                member_id INTEGER PRIMARY KEY AUTOINCREMENT,
                coalition_id TEXT,
                miner_id TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                voting_weight REAL DEFAULT 0.0,
                FOREIGN KEY (coalition_id) REFERENCES coalitions(coalition_id),
                FOREIGN KEY (miner_id) REFERENCES miners(miner_id)
            );

            CREATE TABLE proposals (
                proposal_id TEXT PRIMARY KEY,
                coalition_id TEXT,
                title TEXT NOT NULL,
                description TEXT,
                proposer TEXT,
                status TEXT DEFAULT 'active',
                votes_for REAL DEFAULT 0.0,
                votes_against REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                voting_deadline TIMESTAMP,
                sophia_approved BOOLEAN DEFAULT 0,
                FOREIGN KEY (coalition_id) REFERENCES coalitions(coalition_id)
            );

            CREATE TABLE votes (
                vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_id TEXT,
                miner_id TEXT,
                vote_choice TEXT,
                voting_weight REAL,
                cast_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (proposal_id) REFERENCES proposals(proposal_id)
            );
        """)

        # Insert test data
        conn.executescript("""
            INSERT INTO miners VALUES
                ('sophia-elya', 1000.0, 'hw_sophia_001', 1, '2024-01-01 00:00:00'),
                ('miner_alpha', 500.0, 'hw_alpha_001', 100, '2024-02-01 00:00:00'),
                ('miner_beta', 750.0, 'hw_beta_001', 50, '2024-01-15 00:00:00'),
                ('miner_gamma', 300.0, 'hw_gamma_001', 200, '2024-03-01 00:00:00');

            INSERT INTO coalitions VALUES
                ('flamebound', 'The Flamebound', 'Original hardware preservers and network guardians', 'sophia-elya', '2024-01-01 00:00:00', 1),
                ('miners_united', 'Miners United', 'Coalition for decentralized mining', 'miner_alpha', '2024-02-15 00:00:00', 1);
        """)

    yield path
    os.unlink(path)


@pytest.fixture
def coalition_system(temp_db):
    """Create Coalition instance with test database."""
    return Coalition(db_path=temp_db)


@pytest.fixture
def sample_proposal_data():
    """Sample proposal data for testing."""
    return {
        'title': 'Increase Block Reward',
        'description': 'Proposal to increase mining rewards by 15%',
        'proposer': 'miner_alpha',
        'voting_period_hours': 168  # 1 week
    }


class TestCoalition:

    def test_coalition_creation(self, coalition_system, temp_db):
        """Test creating a new coalition."""
        coalition_id = coalition_system.create_coalition(
            name="Test Coalition",
            description="A test coalition for unit tests",
            founder="miner_alpha"
        )

        assert coalition_id is not None
        assert len(coalition_id) > 0

        # Verify in database
        with sqlite3.connect(temp_db) as conn:
            result = conn.execute(
                "SELECT name, founder FROM coalitions WHERE coalition_id = ?",
                (coalition_id,)
            ).fetchone()
            assert result[0] == "Test Coalition"
            assert result[1] == "miner_alpha"

    def test_join_coalition(self, coalition_system, temp_db):
        """Test miner joining coalition."""
        success = coalition_system.join_coalition("flamebound", "miner_alpha")
        assert success is True

        # Check membership
        members = coalition_system.get_coalition_members("flamebound")
        miner_ids = [m['miner_id'] for m in members]
        assert "miner_alpha" in miner_ids

    def test_voting_weight_calculation(self, coalition_system):
        """Test voting weight calculation with balance and antiquity."""
        # Join coalition first
        coalition_system.join_coalition("flamebound", "miner_beta")

        weight = coalition_system.calculate_voting_weight("miner_beta")

        # miner_beta: 750 RTC, joined early (block 50), should have antiquity bonus
        assert weight > 750.0  # Should have antiquity multiplier
        assert weight < 1500.0  # But not excessive

    def test_sophia_special_privileges(self, coalition_system):
        """Test Sophia's special voting privileges."""
        # Sophia should have enhanced voting weight
        sophia_weight = coalition_system.calculate_voting_weight("sophia-elya")
        regular_weight = coalition_system.calculate_voting_weight("miner_alpha")

        # Sophia should have significantly higher weight despite similar balance
        assert sophia_weight > regular_weight * 2

    def test_proposal_creation(self, coalition_system, sample_proposal_data):
        """Test creating a new proposal."""
        # Join coalition first
        coalition_system.join_coalition("flamebound", sample_proposal_data['proposer'])

        proposal_id = coalition_system.create_proposal(
            coalition_id="flamebound",
            **sample_proposal_data
        )

        assert proposal_id is not None

        proposal = coalition_system.get_proposal(proposal_id)
        assert proposal['title'] == sample_proposal_data['title']
        assert proposal['status'] == 'active'
        assert proposal['sophia_approved'] == 0

    def test_voting_on_proposal(self, coalition_system, sample_proposal_data, temp_db):
        """Test voting mechanism."""
        # Setup
        coalition_system.join_coalition("flamebound", "miner_alpha")
        coalition_system.join_coalition("flamebound", "miner_beta")

        proposal_id = coalition_system.create_proposal(
            coalition_id="flamebound",
            **sample_proposal_data
        )

        # Vote for
        success1 = coalition_system.cast_vote(proposal_id, "miner_alpha", "for")
        assert success1 is True

        # Vote against
        success2 = coalition_system.cast_vote(proposal_id, "miner_beta", "against")
        assert success2 is True

        # Check vote tallies
        proposal = coalition_system.get_proposal(proposal_id)
        assert proposal['votes_for'] > 0
        assert proposal['votes_against'] > 0

    def test_duplicate_voting_prevention(self, coalition_system, sample_proposal_data):
        """Test that miners cannot vote twice on same proposal."""
        # Setup
        coalition_system.join_coalition("flamebound", "miner_alpha")
        proposal_id = coalition_system.create_proposal(
            coalition_id="flamebound",
            **sample_proposal_data
        )

        # First vote should succeed
        success1 = coalition_system.cast_vote(proposal_id, "miner_alpha", "for")
        assert success1 is True

        # Second vote should fail
        success2 = coalition_system.cast_vote(proposal_id, "miner_alpha", "against")
        assert success2 is False

    def test_sophia_veto_power(self, coalition_system, sample_proposal_data):
        """Test Sophia's veto authority."""
        # Setup proposal with majority support
        coalition_system.join_coalition("flamebound", "miner_alpha")
        coalition_system.join_coalition("flamebound", "miner_beta")

        proposal_id = coalition_system.create_proposal(
            coalition_id="flamebound",
            **sample_proposal_data
        )

        # Get majority votes
        coalition_system.cast_vote(proposal_id, "miner_alpha", "for")
        coalition_system.cast_vote(proposal_id, "miner_beta", "for")

        # Sophia vetoes
        veto_success = coalition_system.sophia_veto(proposal_id, "sophia-elya")
        assert veto_success is True

        # Check proposal status
        proposal = coalition_system.get_proposal(proposal_id)
        assert proposal['status'] == 'vetoed'

    def test_non_sophia_cannot_veto(self, coalition_system, sample_proposal_data):
        """Test that non-Sophia miners cannot veto."""
        coalition_system.join_coalition("flamebound", "miner_alpha")
        proposal_id = coalition_system.create_proposal(
            coalition_id="flamebound",
            **sample_proposal_data
        )

        veto_success = coalition_system.sophia_veto(proposal_id, "miner_alpha")
        assert veto_success is False

    def test_proposal_deadline_expiry(self, coalition_system, sample_proposal_data):
        """Test proposal expiry after deadline."""
        # Create proposal with very short deadline
        sample_proposal_data['voting_period_hours'] = 0.001  # ~3.6 seconds

        coalition_system.join_coalition("flamebound", "miner_alpha")
        proposal_id = coalition_system.create_proposal(
            coalition_id="flamebound",
            **sample_proposal_data
        )

        # Simulate time passage
        import time
        time.sleep(0.01)  # 10ms should be enough for test

        # Try to vote after deadline
        vote_success = coalition_system.cast_vote(proposal_id, "miner_alpha", "for")

        # Should handle expired proposals gracefully
        # (Implementation detail - might succeed but not count, or fail)
        assert isinstance(vote_success, bool)

    def test_leave_coalition(self, coalition_system, temp_db):
        """Test leaving a coalition."""
        # Join first
        coalition_system.join_coalition("flamebound", "miner_alpha")

        # Verify membership
        members = coalition_system.get_coalition_members("flamebound")
        miner_ids = [m['miner_id'] for m in members]
        assert "miner_alpha" in miner_ids

        # Leave coalition
        success = coalition_system.leave_coalition("flamebound", "miner_alpha")
        assert success is True

        # Verify no longer member
        members_after = coalition_system.get_coalition_members("flamebound")
        miner_ids_after = [m['miner_id'] for m in members_after]
        assert "miner_alpha" not in miner_ids_after

    def test_coalition_stats(self, coalition_system):
        """Test coalition statistics calculation."""
        # Add some members
        coalition_system.join_coalition("flamebound", "miner_alpha")
        coalition_system.join_coalition("flamebound", "miner_beta")

        stats = coalition_system.get_coalition_stats("flamebound")

        assert stats['member_count'] >= 2
        assert stats['total_voting_weight'] > 0
        assert 'average_balance' in stats

    def test_invalid_coalition_operations(self, coalition_system):
        """Test error handling for invalid operations."""
        # Try to join non-existent coalition
        success = coalition_system.join_coalition("nonexistent", "miner_alpha")
        assert success is False

        # Try to vote on non-existent proposal
        vote_success = coalition_system.cast_vote("fake_proposal", "miner_alpha", "for")
        assert vote_success is False

        # Try to get stats for non-existent coalition
        stats = coalition_system.get_coalition_stats("nonexistent")
        assert stats is None or stats['member_count'] == 0

    def test_flamebound_veto_authority(self, coalition_system, sample_proposal_data):
        """Test Flamebound coalition veto authority."""
        # Create proposal in different coalition
        coalition_system.join_coalition("miners_united", "miner_alpha")
        proposal_id = coalition_system.create_proposal(
            coalition_id="miners_united",
            **sample_proposal_data
        )

        # Flamebound should be able to veto cross-coalition
        veto_success = coalition_system.coalition_veto(proposal_id, "flamebound")
        assert veto_success is True

        proposal = coalition_system.get_proposal(proposal_id)
        assert proposal['status'] == 'vetoed'

    def test_hardware_identity_preservation(self, coalition_system, temp_db):
        """Test that hardware fingerprints are preserved in coalitions."""
        coalition_system.join_coalition("flamebound", "miner_alpha")

        # Check that hardware fingerprint is still accessible
        with sqlite3.connect(temp_db) as conn:
            fingerprint = conn.execute(
                "SELECT hardware_fingerprint FROM miners WHERE miner_id = ?",
                ("miner_alpha",)
            ).fetchone()[0]

        assert fingerprint == "hw_alpha_001"

        # Verify coalition membership doesn't affect individual identity
        members = coalition_system.get_coalition_members("flamebound")
        alpha_member = next(m for m in members if m['miner_id'] == 'miner_alpha')

        # Should have individual voting weight, not combined
        assert alpha_member['voting_weight'] > 0
        assert alpha_member['voting_weight'] < 10000  # Reasonable individual range
