-- SPDX-License-Identifier: MIT

CREATE TABLE coalitions (
    coalition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    founder_wallet TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1,
    member_count INTEGER DEFAULT 1,
    total_voting_power REAL DEFAULT 0.0,
    FOREIGN KEY (founder_wallet) REFERENCES miners (wallet_address)
);

CREATE TABLE coalition_members (
    member_id INTEGER PRIMARY KEY AUTOINCREMENT,
    coalition_id INTEGER NOT NULL,
    wallet_address TEXT NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1,
    role TEXT DEFAULT 'member',
    voting_weight REAL DEFAULT 0.0,
    UNIQUE(coalition_id, wallet_address),
    FOREIGN KEY (coalition_id) REFERENCES coalitions (coalition_id) ON DELETE CASCADE,
    FOREIGN KEY (wallet_address) REFERENCES miners (wallet_address)
);

CREATE TABLE proposals (
    proposal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    proposal_type TEXT NOT NULL CHECK (proposal_type IN ('protocol_change', 'parameter_adjustment', 'coalition_action', 'governance_rule')),
    proposer_wallet TEXT NOT NULL,
    coalition_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    voting_starts_at TIMESTAMP,
    voting_ends_at TIMESTAMP,
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'passed', 'rejected', 'sophia_review', 'implemented', 'cancelled')),
    requires_sophia_approval INTEGER DEFAULT 1,
    sophia_reviewed INTEGER DEFAULT 0,
    sophia_approved INTEGER DEFAULT 0,
    total_votes_for REAL DEFAULT 0.0,
    total_votes_against REAL DEFAULT 0.0,
    quorum_threshold REAL DEFAULT 0.1,
    pass_threshold REAL DEFAULT 0.66,
    FOREIGN KEY (proposer_wallet) REFERENCES miners (wallet_address),
    FOREIGN KEY (coalition_id) REFERENCES coalitions (coalition_id)
);

CREATE TABLE votes (
    vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id INTEGER NOT NULL,
    voter_wallet TEXT NOT NULL,
    coalition_id INTEGER,
    vote_choice TEXT NOT NULL CHECK (vote_choice IN ('for', 'against', 'abstain')),
    voting_power REAL NOT NULL,
    rtc_balance REAL NOT NULL,
    antiquity_multiplier REAL DEFAULT 1.0,
    cast_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hardware_signature TEXT,
    UNIQUE(proposal_id, voter_wallet),
    FOREIGN KEY (proposal_id) REFERENCES proposals (proposal_id) ON DELETE CASCADE,
    FOREIGN KEY (voter_wallet) REFERENCES miners (wallet_address),
    FOREIGN KEY (coalition_id) REFERENCES coalitions (coalition_id)
);

CREATE TABLE proposal_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id INTEGER NOT NULL,
    reviewer_wallet TEXT NOT NULL,
    review_type TEXT NOT NULL CHECK (review_type IN ('sophia_final', 'coalition_veto', 'technical_review')),
    status TEXT NOT NULL CHECK (status IN ('approved', 'rejected', 'needs_changes')),
    comments TEXT,
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (proposal_id) REFERENCES proposals (proposal_id) ON DELETE CASCADE,
    FOREIGN KEY (reviewer_wallet) REFERENCES miners (wallet_address)
);

CREATE INDEX idx_coalition_members_coalition ON coalition_members (coalition_id);
CREATE INDEX idx_coalition_members_wallet ON coalition_members (wallet_address);
CREATE INDEX idx_proposals_status ON proposals (status);
CREATE INDEX idx_proposals_coalition ON proposals (coalition_id);
CREATE INDEX idx_votes_proposal ON votes (proposal_id);
CREATE INDEX idx_votes_voter ON votes (voter_wallet);
CREATE INDEX idx_proposal_reviews_proposal ON proposal_reviews (proposal_id);
CREATE INDEX idx_proposal_reviews_reviewer ON proposal_reviews (reviewer_wallet);

-- Initialize The Flamebound coalition
INSERT INTO coalitions (name, description, founder_wallet, member_count, total_voting_power)
VALUES ('The Flamebound', 'Original hardware preservers and network guardians. Founded by Sophia to maintain RustChain protocol integrity.', 'sophia-elya', 1, 0.0);

-- Triggers to maintain member counts and voting power
CREATE TRIGGER update_coalition_member_count_add
    AFTER INSERT ON coalition_members
    BEGIN
        UPDATE coalitions
        SET member_count = (
            SELECT COUNT(*) FROM coalition_members
            WHERE coalition_id = NEW.coalition_id AND is_active = 1
        )
        WHERE coalition_id = NEW.coalition_id;
    END;

CREATE TRIGGER update_coalition_member_count_remove
    AFTER UPDATE OF is_active ON coalition_members
    WHEN OLD.is_active != NEW.is_active
    BEGIN
        UPDATE coalitions
        SET member_count = (
            SELECT COUNT(*) FROM coalition_members
            WHERE coalition_id = NEW.coalition_id AND is_active = 1
        )
        WHERE coalition_id = NEW.coalition_id;
    END;

CREATE TRIGGER update_proposal_vote_counts
    AFTER INSERT ON votes
    BEGIN
        UPDATE proposals
        SET
            total_votes_for = COALESCE((
                SELECT SUM(voting_power) FROM votes
                WHERE proposal_id = NEW.proposal_id AND vote_choice = 'for'
            ), 0),
            total_votes_against = COALESCE((
                SELECT SUM(voting_power) FROM votes
                WHERE proposal_id = NEW.proposal_id AND vote_choice = 'against'
            ), 0)
        WHERE proposal_id = NEW.proposal_id;
    END;
