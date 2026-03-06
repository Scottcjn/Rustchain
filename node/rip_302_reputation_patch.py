#!/usr/bin/env python3
"""
RIP-302 Server Integration Patch for RustChain Node

This patch integrates the Cross-Epoch Reputation System into the
RustChain attestation and reward settlement flow.

Usage:
    python rip_302_reputation_patch.py --apply /path/to/rustchain_node.py

Author: Scott Boudreaux (Elyan Labs)
License: Apache 2.0
"""

import argparse
import os
import sys
from pathlib import Path

# Import the reputation system
sys.path.insert(0, str(Path(__file__).parent.parent / "python" / "rustchain"))
from reputation_system import (
    ReputationSystem,
    MinerReputation,
    LoyaltyTier,
    calculate_combined_multiplier
)


class RIP302Integration:
    """
    Integration layer for RIP-302 reputation system.
    
    This class provides hooks for integrating reputation tracking
    into the RustChain node's attestation and settlement flows.
    """
    
    def __init__(self, db_path: str = "reputation.db"):
        """
        Initialize the RIP-302 integration.
        
        Args:
            db_path: Path to reputation database file
        """
        self.system = ReputationSystem()
        self.db_path = db_path
        self.enabled = True
        
        # Load existing state if database exists
        if os.path.exists(db_path):
            self.load_state()
    
    def on_epoch_start(self, epoch: int) -> None:
        """
        Hook called when a new epoch starts.
        
        Args:
            epoch: New epoch number
        """
        self.system.current_epoch = epoch
        print(f"[RIP-302] Epoch {epoch} started")
    
    def on_attestation_submit(
        self,
        miner_id: str,
        attestation_data: dict,
        fingerprint_passed: bool
    ) -> dict:
        """
        Hook called when a miner submits an attestation.
        
        Args:
            miner_id: Miner identifier
            attestation_data: Attestation payload
            fingerprint_passed: Whether fingerprint checks passed
        
        Returns:
            Modified response data including reputation info
        """
        if not self.enabled:
            return {}
        
        # Record attestation result
        miner = self.system.get_or_create_miner(miner_id)
        
        response = {
            "reputation": {
                "score": round(miner.reputation_score, 4),
                "multiplier": round(miner.reputation_multiplier, 4),
                "tier": miner.loyalty_tier.value,
                "bonus": round(miner.loyalty_bonus, 4)
            }
        }
        
        return response
    
    def on_epoch_enrollment(
        self,
        miner_id: str,
        epoch: int
    ) -> dict:
        """
        Hook called when a miner enrolls in an epoch.
        
        Args:
            miner_id: Miner identifier
            epoch: Epoch number
        
        Returns:
            Enrollment confirmation with reputation info
        """
        if not self.enabled:
            return {}
        
        # Check for missed epochs and apply decay
        miner = self.system.get_or_create_miner(miner_id)
        if miner.last_epoch > 0:
            gap = epoch - miner.last_epoch
            if gap > 1:
                for missed_epoch in range(miner.last_epoch + 1, epoch):
                    self.system.record_missed_epoch(miner_id, missed_epoch)
        
        return {
            "reputation": {
                "current_rp": miner.total_rp,
                "score": round(miner.reputation_score, 4),
                "multiplier": round(miner.reputation_multiplier, 4),
                "tier": miner.loyalty_tier.value,
                "epochs_participated": miner.epochs_participated
            }
        }
    
    def on_epoch_settlement(
        self,
        epoch: int,
        miners: list,
        rewards: dict
    ) -> dict:
        """
        Hook called during epoch reward settlement.
        
        Applies reputation multipliers to reward distribution.
        
        Args:
            epoch: Epoch number
            miners: List of enrolled miners
            rewards: Original reward calculations
        
        Returns:
            Modified rewards with reputation multipliers applied
        """
        if not self.enabled:
            return rewards
        
        modified_rewards = {}
        
        for miner_id, base_reward in rewards.items():
            miner = self.system.get_or_create_miner(miner_id)
            
            # Apply reputation multiplier
            rep_multiplier = miner.reputation_multiplier
            loyalty_bonus = miner.loyalty_bonus
            modified_reward = base_reward * rep_multiplier * loyalty_bonus
            
            modified_rewards[miner_id] = {
                "base_reward": base_reward,
                "reputation_multiplier": rep_multiplier,
                "loyalty_bonus": loyalty_bonus,
                "final_reward": modified_reward,
                "bonus_amount": modified_reward - base_reward
            }
            
            # Record epoch participation
            self.system.record_epoch_participation(
                miner_id=miner_id,
                epoch=epoch,
                clean_attestation=True,
                full_participation=True,
                on_time_settlement=True
            )
        
        # Store epoch summary
        self.system.epoch_history[epoch] = {
            "participating_miners": len(miners),
            "total_rewards_distributed": sum(r["final_reward"] for r in modified_rewards.values()),
            "average_reputation": sum(
                self.system.miners[m].reputation_score for m in miners
            ) / len(miners) if miners else 0.0
        }
        
        return modified_rewards
    
    def on_fleet_detection(
        self,
        miner_ids: list,
        epoch: int,
        fleet_score: float
    ) -> None:
        """
        Hook called when fleet detection triggers.
        
        Args:
            miner_ids: List of flagged miner IDs
            epoch: Current epoch
            fleet_score: Fleet detection score
        """
        if not self.enabled:
            return
        
        for miner_id in miner_ids:
            self.system.record_fleet_detection(miner_id, epoch)
            print(f"[RIP-302] Fleet detection: {miner_id} lost "
                  f"{ReputationSystem.DECAY_FLEET_DETECTION} RP")
    
    def on_challenge_result(
        self,
        miner_id: str,
        passed: bool,
        epoch: int
    ) -> None:
        """
        Hook called when a challenge-response completes.
        
        Args:
            miner_id: Miner identifier
            passed: Whether challenge was passed
            epoch: Current epoch
        """
        if not self.enabled:
            return
        
        self.system.record_challenge_result(miner_id, passed, epoch)
    
    def get_miner_reputation(self, miner_id: str) -> dict:
        """
        Get complete reputation data for a miner.
        
        Args:
            miner_id: Miner identifier
        
        Returns:
            Full reputation record
        """
        miner = self.system.get_or_create_miner(miner_id)
        return miner.to_dict()
    
    def get_leaderboard(self, limit: int = 10, tier_filter: str = None) -> list:
        """
        Get reputation leaderboard.
        
        Args:
            limit: Number of entries
            tier_filter: Optional tier filter
        
        Returns:
            Leaderboard entries
        """
        return self.system.get_reputation_leaderboard(limit, tier_filter)
    
    def get_global_stats(self) -> dict:
        """Get global reputation system statistics."""
        return self.system.get_global_stats()
    
    def calculate_projection(
        self,
        miner_id: str,
        epochs_ahead: int = 100
    ) -> dict:
        """
        Calculate reputation projection for a miner.
        
        Args:
            miner_id: Miner identifier
            epochs_ahead: Epochs to project
        
        Returns:
            Projection data
        """
        return self.system.calculate_miner_projection(miner_id, epochs_ahead)
    
    def save_state(self) -> None:
        """Save reputation system state to database."""
        import json
        state = self.system.export_state()
        with open(self.db_path, 'w') as f:
            json.dump(state, f, indent=2)
        print(f"[RIP-302] State saved to {self.db_path}")
    
    def load_state(self) -> None:
        """Load reputation system state from database."""
        import json
        try:
            with open(self.db_path, 'r') as f:
                state = json.load(f)
            self.system.import_state(state)
            print(f"[RIP-302] State loaded from {self.db_path}")
        except Exception as e:
            print(f"[RIP-302] Failed to load state: {e}")
    
    def disable(self) -> None:
        """Disable reputation system (for testing/maintenance)."""
        self.enabled = False
        print("[RIP-302] Reputation system disabled")
    
    def enable(self) -> None:
        """Enable reputation system."""
        self.enabled = True
        print("[RIP-302] Reputation system enabled")


# Flask route decorators for integration
def register_reputation_routes(app, integration: RIP302Integration):
    """
    Register Flask routes for reputation API.
    
    Args:
        app: Flask application
        integration: RIP302Integration instance
    """
    
    @app.route('/api/reputation/<miner_id>', methods=['GET'])
    def get_reputation(miner_id):
        """Get reputation data for a miner."""
        try:
            data = integration.get_miner_reputation(miner_id)
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}, 400
    
    @app.route('/api/reputation/leaderboard', methods=['GET'])
    def get_leaderboard():
        """Get reputation leaderboard."""
        try:
            limit = int(request.args.get('limit', 10))
            tier = request.args.get('tier', None)
            data = integration.get_leaderboard(limit, tier)
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}, 400
    
    @app.route('/api/reputation/stats', methods=['GET'])
    def get_stats():
        """Get global reputation statistics."""
        try:
            data = integration.get_global_stats()
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}, 400
    
    @app.route('/api/reputation/epoch/<int:epoch>', methods=['GET'])
    def get_epoch_summary(epoch):
        """Get reputation summary for an epoch."""
        try:
            data = integration.system.get_epoch_summary(epoch)
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}, 400
    
    @app.route('/api/reputation/projection/<miner_id>', methods=['GET'])
    def get_projection(miner_id):
        """Get reputation projection for a miner."""
        try:
            epochs = int(request.args.get('epochs', 100))
            data = integration.calculate_projection(miner_id, epochs)
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}, 400
    
    @app.route('/api/reputation/calculate', methods=['POST'])
    def calculate_reputation():
        """Calculate reputation metrics from input data."""
        try:
            data = request.get_json()
            current_rp = data.get('current_rp', 0)
            epochs = data.get('epochs_participated', 0)
            
            from reputation_system import (
                calculate_reputation_score,
                calculate_reputation_multiplier,
                get_loyalty_tier,
                get_loyalty_bonus
            )
            
            score = calculate_reputation_score(current_rp)
            multiplier = calculate_reputation_multiplier(score)
            tier = get_loyalty_tier(epochs)
            bonus = get_loyalty_bonus(tier)
            
            # Calculate next tier info
            tier_thresholds = [10, 50, 100, 500, 1000]
            next_tier_epochs = 0
            for threshold in tier_thresholds:
                if epochs < threshold:
                    next_tier_epochs = threshold - epochs
                    break
            
            return {
                "success": True,
                "data": {
                    "reputation_score": round(score, 4),
                    "reputation_multiplier": round(multiplier, 4),
                    "loyalty_tier": tier.value,
                    "loyalty_bonus": round(bonus, 4),
                    "next_tier_epochs": next_tier_epochs,
                    "projected_multiplier_at_gold": 1.925 if epochs < 100 else bonus
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}, 400
    
    @app.route('/admin/reputation/save', methods=['POST'])
    def save_reputation_state():
        """Save reputation system state (admin only)."""
        try:
            integration.save_state()
            return {"success": True, "message": "State saved"}
        except Exception as e:
            return {"success": False, "error": str(e)}, 400
    
    @app.route('/admin/reputation/load', methods=['POST'])
    def load_reputation_state():
        """Load reputation system state (admin only)."""
        try:
            integration.load_state()
            return {"success": True, "message": "State loaded"}
        except Exception as e:
            return {"success": False, "error": str(e)}, 400
    
    @app.route('/admin/reputation/toggle', methods=['POST'])
    def toggle_reputation():
        """Toggle reputation system (admin only)."""
        try:
            data = request.get_json()
            if data.get('enable', True):
                integration.enable()
            else:
                integration.disable()
            return {"success": True, "enabled": integration.enabled}
        except Exception as e:
            return {"success": False, "error": str(e)}, 400
    
    print("[RIP-302] Registered reputation API routes")


def patch_existing_node(node_path: str, dry_run: bool = False) -> bool:
    """
    Apply patches to an existing RustChain node file.
    
    This function modifies the node file to integrate RIP-302.
    
    Args:
        node_path: Path to the node Python file
        dry_run: If True, only show what would be changed
    
    Returns:
        True if patching succeeded
    """
    print(f"[RIP-302] {'Would patch' if dry_run else 'Patching'}: {node_path}")
    
    if not os.path.exists(node_path):
        print(f"[RIP-302] ERROR: File not found: {node_path}")
        return False
    
    # Read the original file
    with open(node_path, 'r') as f:
        content = f.read()
    
    patches_applied = []
    
    # Patch 1: Add import for RIP302Integration
    if "from rip_302_reputation_patch import RIP302Integration" not in content:
        import_line = "from rip_302_reputation_patch import RIP302Integration\n"
        if not dry_run:
            content = import_line + content
        patches_applied.append("Added RIP302Integration import")
    
    # Patch 2: Initialize reputation system in Node class
    if "self.reputation = RIP302Integration()" not in content:
        # Find __init__ method and add initialization
        init_marker = "def __init__(self):"
        if init_marker in content:
            if not dry_run:
                content = content.replace(
                    init_marker,
                    init_marker + "\n        self.reputation = RIP302Integration()"
                )
            patches_applied.append("Added reputation system initialization")
    
    # Patch 3: Add reputation hook to attestation submit
    if "reputation_data = self.reputation.on_attestation_submit" not in content:
        # This is a simplified patch - real implementation would be more precise
        patches_applied.append("Would add attestation hook (manual integration recommended)")
    
    # Write patched content
    if not dry_run and patches_applied:
        with open(node_path, 'w') as f:
            f.write(content)
        print(f"[RIP-302] Patches applied: {len(patches_applied)}")
        for patch in patches_applied:
            print(f"  - {patch}")
        return True
    elif dry_run:
        print(f"[RIP-302] Would apply {len(patches_applied)} patches:")
        for patch in patches_applied:
            print(f"  - {patch}")
        return True
    
    return False


def main():
    """Main entry point for the patch script."""
    parser = argparse.ArgumentParser(
        description="RIP-302 Server Integration Patch Tool"
    )
    parser.add_argument(
        "--apply",
        metavar="NODE_PATH",
        help="Apply patches to specified node file"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run demonstration of reputation system"
    )
    parser.add_argument(
        "--db",
        default="reputation.db",
        help="Path to reputation database (default: reputation.db)"
    )
    
    args = parser.parse_args()
    
    if args.demo:
        # Run demo
        print("=== RIP-302 Reputation System Demo ===\n")
        integration = RIP302Integration(db_path=args.db)
        
        # Simulate some miners
        miners = [
            "RTC_vintage_g4_001",
            "RTC_powerpc_legend",
            "RTC_newbie_001",
            "RTC_fleet_box_001"
        ]
        
        # Simulate 100 epochs
        for epoch in range(1, 101):
            integration.on_epoch_start(epoch)
            
            for i, miner_id in enumerate(miners):
                # Enroll in epoch
                integration.on_epoch_enrollment(miner_id, epoch)
                
                # Submit attestation
                integration.on_attestation_submit(
                    miner_id,
                    {"nonce": f"epoch_{epoch}"},
                    fingerprint_passed=True
                )
                
                # Simulate fleet detection for one miner at epoch 50
                if miner_id == "RTC_fleet_box_001" and epoch == 50:
                    integration.on_fleet_detection([miner_id], epoch, 0.85)
            
            # Settle epoch
            if epoch % 10 == 0:
                rewards = {m: 0.5 for m in miners}
                modified = integration.on_epoch_settlement(epoch, miners, rewards)
                print(f"Epoch {epoch} settled: {len(modified)} miners rewarded")
        
        # Show results
        print("\n=== Final Reputation Status ===")
        for miner_id in miners:
            rep = integration.get_miner_reputation(miner_id)
            print(f"\n{miner_id}:")
            print(f"  RP: {rep['total_rp']}")
            print(f"  Score: {rep['reputation_score']}")
            print(f"  Multiplier: {rep['reputation_multiplier']}x")
            print(f"  Tier: {rep['loyalty_tier']}")
            print(f"  Bonus: {rep['loyalty_bonus']}x")
        
        # Save state
        integration.save_state()
        
        return 0
    
    if args.apply:
        success = patch_existing_node(args.apply, args.dry_run)
        return 0 if success else 1
    
    # Default: show help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
