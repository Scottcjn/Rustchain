#!/usr/bin/env python3
"""
RIP-302 Reputation System - Runnable Demonstration

This script demonstrates the Cross-Epoch Reputation & Loyalty Rewards system
with interactive scenarios showing how reputation affects mining rewards.

Usage:
    python examples/reputation_demo.py

Author: Scott Boudreaux (Elyan Labs)
License: Apache 2.0
"""

import sys
import json
from pathlib import Path

# Add the reputation system to path
sys.path.insert(0, str(Path(__file__).parent.parent / "rips" / "python" / "rustchain"))

from reputation_system import (
    ReputationSystem,
    MinerReputation,
    LoyaltyTier,
    calculate_combined_multiplier,
    calculate_reputation_score,
    calculate_reputation_multiplier,
    get_loyalty_tier,
    get_loyalty_bonus
)


def print_header(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def print_subheader(title: str):
    """Print a formatted subsection header."""
    print(f"\n--- {title} ---")


def scenario_1_basic_reputation():
    """
    Scenario 1: Basic Reputation Accumulation
    
    Shows how a miner accumulates reputation over time through
    consistent epoch participation.
    """
    print_header("Scenario 1: Basic Reputation Accumulation")
    
    system = ReputationSystem()
    miner_id = "RTC_vintage_g4_001"
    
    print(f"\nMiner: {miner_id}")
    print("Hardware: PowerMac G4 (PowerPC G4 @ 1GHz)")
    print("Antiquity Multiplier: 2.5x")
    print("\nSimulating 150 epochs of participation...\n")
    
    # Track progression
    milestones = [1, 10, 25, 50, 75, 100, 150]
    progression = []
    
    for epoch in range(1, 151):
        system.current_epoch = epoch
        system.record_epoch_participation(
            miner_id=miner_id,
            epoch=epoch,
            clean_attestation=True,
            full_participation=True,
            on_time_settlement=True
        )
        
        if epoch in milestones:
            miner = system.get_or_create_miner(miner_id)
            progression.append({
                "epoch": epoch,
                "rp": miner.total_rp,
                "score": miner.reputation_score,
                "multiplier": miner.reputation_multiplier,
                "tier": miner.loyalty_tier.value,
                "bonus": miner.loyalty_bonus
            })
    
    # Display progression table
    print(f"{'Epoch':>6} | {'RP':>5} | {'Score':>6} | {'Rep Mult':>8} | {'Tier':>10} | {'Bonus':>7}")
    print("-" * 60)
    
    for p in progression:
        print(f"{p['epoch']:>6} | {p['rp']:>5} | {p['score']:>6.2f} | "
              f"{p['multiplier']:>8.4f}x | {p['tier']:>10} | {p['bonus']:>7.2f}x")
    
    # Final status
    miner = system.get_or_create_miner(miner_id)
    print_subheader("Final Status (Epoch 150)")
    print(f"Total RP Earned: {miner.total_rp}")
    print(f"Reputation Score: {miner.reputation_score:.4f}")
    print(f"Reputation Multiplier: {miner.reputation_multiplier:.4f}x")
    print(f"Loyalty Tier: {miner.loyalty_tier.value}")
    print(f"Loyalty Bonus: {miner.loyalty_bonus:.4f}x")
    print(f"Combined Multiplier: {miner.combined_multiplier:.4f}x")
    print(f"Epochs to Next Tier: {miner.epochs_to_next_tier}")
    
    # Calculate reward impact
    base_reward = 0.5  # RTC per epoch
    base_total = base_reward * 150
    with_rep = sum([
        base_reward * (1.0 + ((1.0 + (ep * 7 / 100) - 1.0) * 0.25)) * 
        (1.05 if ep >= 10 else 1.0) * (1.10 if ep >= 50 else 1.0) * (1.20 if ep >= 100 else 1.0)
        for ep in range(1, 151)
    ])
    
    print_subheader("Reward Impact")
    print(f"Base Rewards (no rep): {base_total:.2f} RTC")
    print(f"With Reputation: ~{with_rep:.2f} RTC")
    print(f"Bonus Earned: ~{with_rep - base_total:.2f} RTC ({((with_rep/base_total)-1)*100:.1f}% increase)")


def scenario_2_loyalty_tiers():
    """
    Scenario 2: Loyalty Tier Progression
    
    Shows the bonus progression through loyalty tiers.
    """
    print_header("Scenario 2: Loyalty Tier Progression")
    
    print("\nLoyalty tiers reward long-term participation:\n")
    
    tiers = [
        (0, "None", 1.00),
        (10, "Bronze", 1.05),
        (50, "Silver", 1.10),
        (100, "Gold", 1.20),
        (500, "Platinum", 1.50),
        (1000, "Diamond", 2.00)
    ]
    
    print(f"{'Epochs':>8} | {'Tier':>10} | {'Bonus':>7} | {'Example Reward*':>15}")
    print("-" * 55)
    
    base_reward = 1.0  # Normalized reward
    
    for epochs, tier_name, bonus in tiers:
        example = base_reward * bonus
        tier_display = tier_name if epochs > 0 else "None"
        print(f"{epochs:>8} | {tier_display:>10} | {bonus:>7.2f}x | {example:>13.2f} RTC")
    
    print("\n*Example shows reward for a miner with 2.5x antiquity multiplier")
    print("  at a fixed reputation score of 3.0 (1.5x rep multiplier)")
    
    # Show combined effect
    print_subheader("Combined Multiplier Example")
    print("\nMiner with 2.5x antiquity multiplier:")
    
    antiquity = 2.5
    rep_score = 3.0  # 200 epochs
    rep_mult = calculate_reputation_multiplier(rep_score)
    
    for epochs, tier_name, bonus in tiers[1:]:  # Skip "None" tier
        combined = antiquity * rep_mult * bonus
        print(f"  {tier_name:>10} ({epochs:>3} epochs): {combined:.4f}x total multiplier")


def scenario_3_decay_events():
    """
    Scenario 3: Reputation Decay
    
    Shows how reputation decays from various negative events.
    """
    print_header("Scenario 3: Reputation Decay & Recovery")
    
    system = ReputationSystem()
    miner_id = "RTC_problematic_miner"
    
    print(f"\nMiner: {miner_id}")
    print("Scenario: Miner encounters various issues over 100 epochs\n")
    
    # Phase 1: Good participation (epochs 1-30)
    print("Phase 1: Epochs 1-30 (Clean participation)")
    for epoch in range(1, 31):
        system.current_epoch = epoch
        system.record_epoch_participation(
            miner_id=miner_id,
            epoch=epoch,
            clean_attestation=True,
            full_participation=True,
            on_time_settlement=True
        )
    
    miner = system.get_or_create_miner(miner_id)
    print(f"  RP after Phase 1: {miner.total_rp}")
    
    # Phase 2: Missed epoch (epoch 31)
    print("\nPhase 2: Epoch 31 (Missed epoch)")
    system.record_missed_epoch(miner_id, 31)
    miner = system.get_or_create_miner(miner_id)
    print(f"  Decay: -{ReputationSystem.DECAY_MISSED_EPOCH} RP")
    print(f"  RP after decay: {miner.total_rp}")
    
    # Phase 3: Recovery with bonus (epochs 32-41)
    print("\nPhase 3: Epochs 32-41 (Recovery period with 1.5x RP bonus)")
    for epoch in range(32, 42):
        system.current_epoch = epoch
        system.record_epoch_participation(
            miner_id=miner_id,
            epoch=epoch,
            clean_attestation=True,
            full_participation=True,
            on_time_settlement=True
        )
    
    miner = system.get_or_create_miner(miner_id)
    print(f"  RP after recovery: {miner.total_rp}")
    
    # Phase 4: Failed attestation (epoch 42)
    print("\nPhase 4: Epoch 42 (Failed attestation)")
    system.record_epoch_participation(
        miner_id=miner_id,
        epoch=42,
        clean_attestation=False,
        full_participation=True,
        on_time_settlement=True
    )
    miner = system.get_or_create_miner(miner_id)
    print(f"  Decay: -{ReputationSystem.DECAY_FAILED_ATTESTATION} RP")
    print(f"  RP after decay: {miner.total_rp}")
    
    # Phase 5: Fleet detection (epoch 50)
    print("\nPhase 5: Epoch 50 (Fleet detection - severe penalty)")
    system.record_fleet_detection(miner_id, 50)
    miner = system.get_or_create_miner(miner_id)
    print(f"  Decay: -{ReputationSystem.DECAY_FLEET_DETECTION} RP")
    print(f"  RP after decay: {miner.total_rp}")
    
    # Phase 6: Continued participation (epochs 51-100)
    print("\nPhase 6: Epochs 51-100 (Continued participation)")
    for epoch in range(51, 101):
        system.current_epoch = epoch
        system.record_epoch_participation(
            miner_id=miner_id,
            epoch=epoch,
            clean_attestation=True,
            full_participation=True,
            on_time_settlement=True
        )
    
    miner = system.get_or_create_miner(miner_id)
    
    # Summary
    print_subheader("Decay Event Summary")
    print(f"{'Event':<25} | {'Epoch':>6} | {'RP Lost':>8} | {'RP After':>10}")
    print("-" * 55)
    
    for event in miner.decay_events:
        print(f"{event.reason:<25} | {event.epoch:>6} | {event.rp_lost:>8} | {event.new_rp:>10}")
    
    print(f"\nFinal Status (Epoch 100):")
    print(f"  Total RP: {miner.total_rp}")
    print(f"  Reputation Score: {miner.reputation_score:.4f}")
    print(f"  Reputation Multiplier: {miner.reputation_multiplier:.4f}x")
    print(f"  Loyalty Tier: {miner.loyalty_tier.value}")
    print(f"  Decay Events: {len(miner.decay_events)}")
    
    # Compare with clean miner
    clean_system = ReputationSystem()
    for epoch in range(1, 101):
        clean_system.current_epoch = epoch
        clean_system.record_epoch_participation(
            miner_id="clean_miner",
            epoch=epoch,
            clean_attestation=True,
            full_participation=True,
            on_time_settlement=True
        )
    
    clean_miner = clean_system.get_or_create_miner("clean_miner")
    print_subheader("Comparison with Clean Miner")
    print(f"Problematic miner RP: {miner.total_rp}")
    print(f"Clean miner RP: {clean_miner.total_rp}")
    print(f"Difference: {clean_miner.total_rp - miner.total_rp} RP ({((clean_miner.total_rp/miner.total_rp)-1)*100:.1f}% more)")


def scenario_4_reward_distribution():
    """
    Scenario 4: Reputation-Weighted Reward Distribution
    
    Shows how reputation affects actual reward distribution in an epoch.
    """
    print_header("Scenario 4: Reputation-Weighted Reward Distribution")
    
    print("\nSimulating epoch settlement with 5 miners of varying reputation:\n")
    
    # Create miners with different profiles
    miners_data = [
        {
            "id": "RTC_legend_001",
            "desc": "Diamond tier legend",
            "epochs": 1200,
            "rp": 500,  # Capped
            "antiquity": 2.8
        },
        {
            "id": "RTC_veteran_g4",
            "desc": "Gold tier veteran",
            "epochs": 150,
            "rp": 300,
            "antiquity": 2.5
        },
        {
            "id": "RTC_silver_ppc",
            "desc": "Silver tier regular",
            "epochs": 60,
            "rp": 150,
            "antiquity": 2.6
        },
        {
            "id": "RTC_bronze_new",
            "desc": "Bronze tier newcomer",
            "epochs": 15,
            "rp": 40,
            "antiquity": 2.3
        },
        {
            "id": "RTC_fresh_001",
            "desc": "Brand new miner",
            "epochs": 1,
            "rp": 7,
            "antiquity": 1.0
        }
    ]
    
    epoch_pot = 1.5  # RTC
    num_buckets = 3  # Assume 3 active buckets
    bucket_share = epoch_pot / num_buckets  # 0.5 RTC per bucket
    
    print(f"Epoch Pot: {epoch_pot} RTC")
    print(f"Active Buckets: {num_buckets}")
    print(f"Bucket Share: {bucket_share:.4f} RTC\n")
    
    # Calculate weighted distribution
    total_weighted = 0
    miner_weights = []
    
    for m in miners_data:
        rep_score = calculate_reputation_score(m["rp"])
        rep_mult = calculate_reputation_multiplier(rep_score)
        tier = get_loyalty_tier(m["epochs"])
        loyalty_bonus = get_loyalty_bonus(tier)
        
        weight = m["antiquity"] * rep_mult * loyalty_bonus
        total_weighted += weight
        
        miner_weights.append({
            **m,
            "rep_score": rep_score,
            "rep_mult": rep_mult,
            "loyalty_bonus": loyalty_bonus,
            "weight": weight
        })
    
    # Display calculation
    print(f"{'Miner':<20} | {'Antiq':>6} | {'Rep':>6} | {'Loyalty':>8} | {'Weight':>8} | {'Share':>10}")
    print("-" * 75)
    
    for m in miner_weights:
        share = (m["weight"] / total_weighted) * bucket_share
        print(f"{m['id']:<20} | {m['antiquity']:>6.1f}x | {m['rep_mult']:>6.4f}x | "
              f"{m['loyalty_bonus']:>8.2f}x | {m['weight']:>8.4f} | {share:>10.4f} RTC")
    
    print("-" * 75)
    print(f"{'Total Weighted':<20} | {'':>6} | {'':>6} | {'':>8} | {total_weighted:>8.4f} | {bucket_share:>10.4f} RTC")
    
    # Show impact comparison
    print_subheader("Impact Analysis")
    print("\nComparison: With vs Without Reputation System\n")
    
    print(f"{'Miner':<20} | {'Base Only':>12} | {'With Rep':>12} | {'Bonus':>12}")
    print("-" * 65)
    
    for m in miner_weights:
        # Base only (antiquity only)
        base_weight = m["antiquity"]
        base_total = sum(miner["antiquity"] for miner in miners_data)
        base_share = (base_weight / base_total) * bucket_share
        
        # With reputation
        rep_share = (m["weight"] / total_weighted) * bucket_share
        
        bonus = rep_share - base_share
        bonus_pct = ((rep_share / base_share) - 1) * 100 if base_share > 0 else 0
        
        print(f"{m['id']:<20} | {base_share:>12.4f} | {rep_share:>12.4f} | "
              f"{bonus:+>11.4f} ({bonus_pct:>5.1f}%)")


def scenario_5_fleet_economics():
    """
    Scenario 5: Fleet Operator Economics
    
    Shows how reputation system makes fleet operations even less profitable.
    """
    print_header("Scenario 5: Fleet Operator Economics")
    
    print("\nComparing solo miner vs fleet operator profitability:\n")
    
    # Solo miner profile
    solo = {
        "id": "RTC_solo_g4",
        "epochs": 500,
        "rp": 400,  # Consistent participation
        "antiquity": 2.5
    }
    
    # Fleet operator profile (500 boxes)
    fleet = {
        "id": "RTC_fleet_operator",
        "boxes": 500,
        "epochs": 50,  # Shorter participation
        "rp": 100,  # Lower per-box due to fleet detection decay
        "antiquity": 1.0  # Modern hardware
    }
    
    # Calculate solo miner metrics
    solo_rep = calculate_reputation_score(solo["rp"])
    solo_mult = calculate_reputation_multiplier(solo_rep)
    solo_tier = get_loyalty_tier(solo["epochs"])
    solo_bonus = get_loyalty_bonus(solo_tier)
    solo_combined = solo["antiquity"] * solo_mult * solo_bonus
    
    # Calculate fleet per-box metrics
    fleet_rep = calculate_reputation_score(fleet["rp"])
    fleet_mult = calculate_reputation_multiplier(fleet_rep)
    fleet_tier = get_loyalty_tier(fleet["epochs"])
    fleet_bonus = get_loyalty_bonus(fleet_tier)
    fleet_combined = fleet["antiquity"] * fleet_mult * fleet_bonus
    
    print("Solo Miner (PowerMac G4):")
    print(f"  Epochs: {solo['epochs']}")
    print(f"  RP: {solo['rp']}")
    print(f"  Antiquity: {solo['antiquity']}x")
    print(f"  Reputation Multiplier: {solo_mult:.4f}x")
    print(f"  Loyalty Tier: {solo_tier.value}")
    print(f"  Loyalty Bonus: {solo_bonus:.2f}x")
    print(f"  Combined Multiplier: {solo_combined:.4f}x")
    
    print(f"\nFleet Operator (500 modern boxes):")
    print(f"  Epochs per box: {fleet['epochs']}")
    print(f"  RP per box: {fleet['rp']}")
    print(f"  Boxes: {fleet['boxes']}")
    print(f"  Antiquity per box: {fleet['antiquity']}x")
    print(f"  Reputation Multiplier per box: {fleet_mult:.4f}x")
    print(f"  Loyalty Tier per box: {fleet_tier.value}")
    print(f"  Loyalty Bonus per box: {fleet_bonus:.2f}x")
    print(f"  Combined Multiplier per box: {fleet_combined:.4f}x")
    
    # Calculate relative profitability
    print_subheader("Relative Profitability")
    
    # Per-box comparison
    print(f"\nPer-Box Comparison:")
    print(f"  Solo miner multiplier: {solo_combined:.4f}x")
    print(f"  Fleet box multiplier: {fleet_combined:.4f}x")
    print(f"  Ratio (solo/fleet): {solo_combined/fleet_combined:.2f}x")
    print(f"  → Solo miner earns {((solo_combined/fleet_combined)-1)*100:.0f}% more per box!")
    
    # Total fleet comparison (with RIP-201 bucket split)
    print(f"\nTotal Operation (with RIP-201 bucket split):")
    
    # Assume both in same bucket for simplicity
    # Fleet detection already applied to RP
    bucket_share = 0.5  # RTC
    
    # Solo gets full bucket share weighted by their multiplier
    solo_share = bucket_share  # Only miner in bucket
    
    # Fleet shares bucket among 500 boxes
    fleet_total_weight = fleet_combined * fleet["boxes"]
    fleet_share = bucket_share  # Shared among all boxes
    fleet_per_box = fleet_share / fleet["boxes"]
    
    print(f"  Solo miner share: {solo_share:.4f} RTC")
    print(f"  Fleet total share: {fleet_share:.4f} RTC")
    print(f"  Fleet per-box share: {fleet_per_box:.6f} RTC")
    print(f"  → Fleet operator earns less per box than solo miner!")
    
    print_subheader("Economic Conclusion")
    print("""
The reputation system compounds the fleet detection penalties:

1. Fleet detection triggers -25 RP decay per box
2. Lower RP → lower reputation multiplier
3. Fewer epochs → lower loyalty tier
4. Combined with RIP-201 bucket split, fleet ROI becomes absurdly low

Result: A $5M fleet operation earns ~$27/year, making the payback
period ~182,648 years. Reputation system makes this even worse for
fleets that try to game the system over time.
""")


def scenario_6_projection():
    """
    Scenario 6: Reputation Projection
    
    Shows projected reputation growth for different participation patterns.
    """
    print_header("Scenario 6: Reputation Projection Calculator")
    
    system = ReputationSystem()
    
    # Create three miner profiles
    profiles = [
        {
            "id": "RTC_dedicated_001",
            "desc": "Dedicated miner (perfect participation)",
            "epochs": 50,
            "rp": 350,  # Good participation
            "project_epochs": 500
        },
        {
            "id": "RTC_casual_001",
            "desc": "Casual miner (70% participation)",
            "epochs": 50,
            "rp": 175,  # Half the RP due to missed epochs
            "project_epochs": 500
        },
        {
            "id": "RTC_intermittent",
            "desc": "Intermittent miner (frequent absences)",
            "epochs": 50,
            "rp": 70,  # Low RP due to absences and decay
            "project_epochs": 500
        }
    ]
    
    print(f"\nProjecting 500 epochs ahead for different miner profiles:\n")
    
    for profile in profiles:
        # Create miner in system
        miner = MinerReputation(
            miner_id=profile["id"],
            total_rp=profile["rp"],
            epochs_participated=profile["epochs"]
        )
        system.miners[profile["id"]] = miner
        
        # Calculate projection
        projection = system.calculate_miner_projection(
            profile["id"],
            profile["project_epochs"]
        )
        
        print(f"{profile['desc']}:")
        print(f"  Current: RP={profile['rp']}, Score={projection['current_score']:.2f}, "
              f"Mult={projection['current_multiplier']:.4f}x")
        print(f"  Projected ({profile['project_epochs']} epochs):")
        print(f"    RP: {projection['projected_rp']}")
        print(f"    Score: {projection['projected_score']:.2f}")
        print(f"    Multiplier: {projection['projected_multiplier']:.4f}x")
        print(f"    Will reach {projection['next_tier']}: {projection['will_reach_tier']}")
        print()
    
    print_subheader("Key Insight")
    print("""
Consistent participation compounds over time. A miner who shows up
every epoch will pull far ahead of one who participates intermittently,
even if they started at the same time.

The recovery bonus (1.5x RP for 10 epochs after decay) helps miners
recover from setbacks, but prevention (consistent participation) is
still the optimal strategy.
""")


def interactive_demo():
    """
    Interactive demonstration allowing user input.
    """
    print_header("Interactive Reputation Calculator")
    
    print("\nEnter your miner statistics to calculate reputation metrics:\n")
    
    try:
        # Get user input
        epochs = int(input("Epochs participated: ").strip() or "50")
        rp = int(input("Total RP earned: ").strip() or "175")
        antiquity = float(input("Antiquity multiplier: ").strip() or "2.5")
        
        # Calculate metrics
        rep_score = calculate_reputation_score(rp)
        rep_mult = calculate_reputation_multiplier(rep_score)
        tier = get_loyalty_tier(epochs)
        loyalty_bonus = get_loyalty_bonus(tier)
        combined = antiquity * rep_mult * loyalty_bonus
        
        # Display results
        print("\n" + "=" * 50)
        print(" Your Reputation Metrics")
        print("=" * 50)
        print(f"Reputation Score: {rep_score:.4f}")
        print(f"Reputation Multiplier: {rep_mult:.4f}x")
        print(f"Loyalty Tier: {tier.value}")
        print(f"Loyalty Bonus: {loyalty_bonus:.2f}x")
        print(f"Combined Multiplier: {combined:.4f}x")
        
        # Calculate next tier
        tier_thresholds = [(10, "Bronze"), (50, "Silver"), (100, "Gold"), 
                          (500, "Platinum"), (1000, "Diamond")]
        for threshold, name in tier_thresholds:
            if epochs < threshold:
                print(f"Epochs to {name}: {threshold - epochs}")
                break
        else:
            print("Max tier achieved! (Diamond)")
        
        # Project forward
        print(f"\nProjection (100 epochs ahead, perfect participation):")
        projected_rp = rp + (ReputationSystem.RP_PER_EPOCH_MAX * 100)
        projected_score = min(5.0, 1.0 + (projected_rp / 100.0))
        projected_mult = 1.0 + ((projected_score - 1.0) * 0.25)
        print(f"  Projected RP: {projected_rp}")
        print(f"  Projected Score: {projected_score:.2f}")
        print(f"  Projected Multiplier: {projected_mult:.4f}x")
        
    except ValueError:
        print("Invalid input. Please enter numeric values.")
    except KeyboardInterrupt:
        print("\n\nDemo cancelled.")
        return
    
    print("\n" + "=" * 50)


def main():
    """Run all demonstration scenarios."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║   RIP-302: Cross-Epoch Reputation & Loyalty Rewards Demo     ║
║                                                              ║
║   This demonstration shows how reputation affects mining     ║
║   rewards in the RustChain network.                          ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Run all scenarios
    scenario_1_basic_reputation()
    scenario_2_loyalty_tiers()
    scenario_3_decay_events()
    scenario_4_reward_distribution()
    scenario_5_fleet_economics()
    scenario_6_projection()
    
    # Optional interactive demo
    print_header("Interactive Demo")
    print("\nWould you like to run the interactive calculator?")
    try:
        response = input("Enter 'y' to continue, any other key to skip: ").strip().lower()
        if response == 'y':
            interactive_demo()
    except KeyboardInterrupt:
        pass
    
    print_header("Demo Complete")
    print("""
For more information, see:
  - RIP-302 Specification: rips/docs/RIP-0302-cross-epoch-reputation.md
  - Python Module: rips/python/rustchain/reputation_system.py
  - Server Integration: node/rip_302_reputation_patch.py
  - Test Suite: tests/test_reputation_system.py
""")


if __name__ == "__main__":
    main()
