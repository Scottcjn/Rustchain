#!/usr/bin/env python3
"""
RIP-302 Reputation CLI Commands

This module adds reputation system commands to the RustChain CLI.

Usage:
    python rustchain_cli.py reputation <miner_id>
    python rustchain_cli.py reputation-leaderboard [--limit N] [--tier TIER]
    python rustchain_cli.py reputation-stats
    python rustchain_cli.py reputation-projection <miner_id> [--epochs N]

Author: Scott Boudreaux (Elyan Labs)
License: Apache 2.0
"""

import argparse
import json
import sys
from pathlib import Path

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "rips" / "python" / "rustchain"))
sys.path.insert(0, str(Path(__file__).parent.parent / "node"))

from reputation_system import (
    ReputationSystem,
    calculate_reputation_score,
    calculate_reputation_multiplier,
    get_loyalty_tier,
    get_loyalty_bonus
)


def cmd_reputation(args):
    """Get reputation data for a specific miner."""
    print(f"=== Reputation for {args.miner_id} ===\n")
    
    # Try to load from node or use demo data
    try:
        from rip_302_reputation_patch import RIP302Integration
        integration = RIP302Integration(db_path=args.db)
        data = integration.get_miner_reputation(args.miner_id)
    except Exception as e:
        # Demo mode with simulated data
        print(f"[Demo Mode] No database found, showing simulated data\n")
        data = {
            "miner_id": args.miner_id,
            "total_rp": 150,
            "reputation_score": 2.5,
            "reputation_multiplier": 1.375,
            "epochs_participated": 75,
            "epochs_consecutive": 12,
            "loyalty_tier": "silver",
            "loyalty_bonus": 1.10,
            "combined_multiplier": 1.5125,
            "last_epoch": 1847,
            "attestation_history": {
                "total": 75,
                "passed": 73,
                "failed": 2,
                "pass_rate": 0.9733
            },
            "challenge_history": {
                "total": 5,
                "passed": 5,
                "failed": 0,
                "pass_rate": 1.0
            },
            "decay_events": []
        }
    
    # Display formatted output
    print(f"Miner ID:           {data.get('miner_id', 'N/A')}")
    print(f"Total RP:           {data.get('total_rp', 0)}")
    print(f"Reputation Score:   {data.get('reputation_score', 0):.4f}")
    print(f"Reputation Mult:    {data.get('reputation_multiplier', 1):.4f}x")
    print(f"Loyalty Tier:       {data.get('loyalty_tier', 'none')}")
    print(f"Loyalty Bonus:      {data.get('loyalty_bonus', 1):.2f}x")
    print(f"Combined Mult:      {data.get('combined_multiplier', 1):.4f}x")
    print(f"Epochs Participated: {data.get('epochs_participated', 0)}")
    print(f"Epochs Consecutive:  {data.get('epochs_consecutive', 0)}")
    print(f"Last Epoch:         {data.get('last_epoch', 0)}")
    
    if 'attestation_history' in data:
        ah = data['attestation_history']
        print(f"\nAttestation History:")
        print(f"  Total:  {ah.get('total', 0)}")
        print(f"  Passed: {ah.get('passed', 0)}")
        print(f"  Failed: {ah.get('failed', 0)}")
        print(f"  Rate:   {ah.get('pass_rate', 1):.2%}")
    
    if 'challenge_history' in data:
        ch = data['challenge_history']
        print(f"\nChallenge History:")
        print(f"  Total:  {ch.get('total', 0)}")
        print(f"  Passed: {ch.get('passed', 0)}")
        print(f"  Failed: {ch.get('failed', 0)}")
        print(f"  Rate:   {ch.get('pass_rate', 1):.2%}")
    
    if data.get('decay_events'):
        print(f"\nDecay Events ({len(data['decay_events'])}):")
        for event in data['decay_events'][-5:]:  # Show last 5
            print(f"  Epoch {event['epoch']}: {event['reason']} (-{event['rp_lost']} RP)")
    
    if args.json:
        print("\n--- JSON Output ---")
        print(json.dumps(data, indent=2))


def cmd_leaderboard(args):
    """Get reputation leaderboard."""
    print(f"=== Reputation Leaderboard ===\n")
    
    try:
        from rip_302_reputation_patch import RIP302Integration
        integration = RIP302Integration(db_path=args.db)
        leaderboard = integration.get_leaderboard(
            limit=args.limit,
            tier_filter=args.tier
        )
    except Exception as e:
        # Demo mode
        print(f"[Demo Mode] Showing simulated leaderboard\n")
        leaderboard = [
            {
                "rank": 1,
                "miner_id": "RTC_powerpc_legend",
                "reputation_score": 5.0,
                "reputation_multiplier": 2.0,
                "loyalty_tier": "diamond",
                "epochs_participated": 1247
            },
            {
                "rank": 2,
                "miner_id": "RTC_vintage_g4_042",
                "reputation_score": 4.8,
                "reputation_multiplier": 1.95,
                "loyalty_tier": "platinum",
                "epochs_participated": 892
            },
            {
                "rank": 3,
                "miner_id": "RTC_snes_miner",
                "reputation_score": 4.2,
                "reputation_multiplier": 1.8,
                "loyalty_tier": "gold",
                "epochs_participated": 234
            }
        ][:args.limit]
    
    # Display table
    print(f"{'Rank':>5} | {'Miner ID':<25} | {'Score':>7} | {'Mult':>7} | {'Tier':>10} | {'Epochs':>8}")
    print("-" * 80)
    
    for entry in leaderboard:
        print(f"#{entry['rank']:>4} | {entry['miner_id']:<25} | "
              f"{entry['reputation_score']:>7.4f} | {entry['reputation_multiplier']:>7.4f}x | "
              f"{entry['loyalty_tier']:>10} | {entry['epochs_participated']:>8}")
    
    if args.json:
        print("\n--- JSON Output ---")
        print(json.dumps(leaderboard, indent=2))


def cmd_stats(args):
    """Get global reputation statistics."""
    print("=== Global Reputation Statistics ===\n")
    
    try:
        from rip_302_reputation_patch import RIP302Integration
        integration = RIP302Integration(db_path=args.db)
        stats = integration.get_global_stats()
    except Exception as e:
        # Demo mode
        print(f"[Demo Mode] Showing simulated statistics\n")
        stats = {
            "current_epoch": 1847,
            "total_miners": 1247,
            "reputation_holders": {
                "diamond": 3,
                "platinum": 18,
                "gold": 142,
                "silver": 389,
                "bronze": 695,
                "none": 0
            },
            "average_reputation_score": 2.34,
            "total_rp_distributed": 1847293
        }
    
    print(f"Current Epoch:      {stats.get('current_epoch', 0)}")
    print(f"Total Miners:       {stats.get('total_miners', 0)}")
    print(f"Avg Rep Score:      {stats.get('average_reputation_score', 0):.4f}")
    print(f"Total RP Distributed: {stats.get('total_rp_distributed', 0):,}")
    
    print("\nTier Distribution:")
    holders = stats.get('reputation_holders', {})
    for tier in ['diamond', 'platinum', 'gold', 'silver', 'bronze', 'none']:
        count = holders.get(tier, 0)
        bar = "█" * min(count, 50)  # Visual bar
        print(f"  {tier:>10}: {count:>5} {bar}")
    
    if args.json:
        print("\n--- JSON Output ---")
        print(json.dumps(stats, indent=2))


def cmd_projection(args):
    """Calculate reputation projection for a miner."""
    print(f"=== Reputation Projection for {args.miner_id} ===\n")
    
    try:
        from rip_302_reputation_patch import RIP302Integration
        integration = RIP302Integration(db_path=args.db)
        projection = integration.calculate_projection(args.miner_id, epochs_ahead=args.epochs)
    except Exception as e:
        # Demo mode
        print(f"[Demo Mode] Showing simulated projection\n")
        projection = {
            "current_rp": 150,
            "current_score": 2.5,
            "current_multiplier": 1.375,
            "projected_rp": 150 + (7 * args.epochs),
            "projected_score": min(5.0, 1.0 + ((150 + 7 * args.epochs) / 100)),
            "projected_multiplier": 0,  # Will calculate below
            "epochs_ahead": args.epochs,
            "epochs_to_next_tier": 25,
            "next_tier": "gold",
            "will_reach_tier": args.epochs >= 25
        }
        projected_score = projection["projected_score"]
        projection["projected_multiplier"] = 1.0 + ((projected_score - 1.0) * 0.25)
    
    print("Current Status:")
    print(f"  RP:              {projection.get('current_rp', 0)}")
    print(f"  Score:           {projection.get('current_score', 0):.4f}")
    print(f"  Multiplier:      {projection.get('current_multiplier', 0):.4f}x")
    
    print(f"\nProjection ({projection.get('epochs_ahead', 0)} epochs ahead):")
    print(f"  Projected RP:    {projection.get('projected_rp', 0)}")
    print(f"  Projected Score: {projection.get('projected_score', 0):.4f}")
    print(f"  Projected Mult:  {projection.get('projected_multiplier', 0):.4f}x")
    
    print(f"\nNext Tier:")
    print(f"  Target:          {projection.get('next_tier', 'N/A')}")
    print(f"  Epochs Needed:   {projection.get('epochs_to_next_tier', 0)}")
    print(f"  Will Reach:      {'Yes' if projection.get('will_reach_tier') else 'No'}")
    
    if args.json:
        print("\n--- JSON Output ---")
        print(json.dumps(projection, indent=2))


def cmd_calculate(args):
    """Calculate reputation metrics from input values."""
    print("=== Reputation Calculator ===\n")
    
    rp = args.rp
    epochs = args.epochs
    
    score = calculate_reputation_score(rp)
    multiplier = calculate_reputation_multiplier(score)
    tier = get_loyalty_tier(epochs)
    bonus = get_loyalty_bonus(tier)
    combined = multiplier * bonus
    
    print(f"Input:")
    print(f"  Total RP:          {rp}")
    print(f"  Epochs:            {epochs}")
    
    print(f"\nResults:")
    print(f"  Reputation Score:  {score:.4f}")
    print(f"  Reputation Mult:   {multiplier:.4f}x")
    print(f"  Loyalty Tier:      {tier.value}")
    print(f"  Loyalty Bonus:     {bonus:.2f}x")
    print(f"  Combined Mult:     {combined:.4f}x")
    
    # Next tier info
    tier_thresholds = [(10, "Bronze"), (50, "Silver"), (100, "Gold"), 
                      (500, "Platinum"), (1000, "Diamond")]
    for threshold, name in tier_thresholds:
        if epochs < threshold:
            print(f"\n  To {name}: {threshold - epochs} epochs needed")
            break
    else:
        print(f"\n  Max tier achieved! (Diamond)")
    
    if args.json:
        result = {
            "input": {"rp": rp, "epochs": epochs},
            "reputation_score": round(score, 4),
            "reputation_multiplier": round(multiplier, 4),
            "loyalty_tier": tier.value,
            "loyalty_bonus": round(bonus, 4),
            "combined_multiplier": round(combined, 4)
        }
        print("\n--- JSON Output ---")
        print(json.dumps(result, indent=2))


def create_parser():
    """Create argument parser for reputation commands."""
    parser = argparse.ArgumentParser(
        description="RIP-302 Reputation System CLI",
        prog="rustchain reputation"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Reputation command
    rep_parser = subparsers.add_parser("reputation", help="Get miner reputation")
    rep_parser.add_argument("miner_id", help="Miner ID to query")
    rep_parser.add_argument("--db", default="reputation.db", help="Database path")
    rep_parser.add_argument("--json", action="store_true", help="Output as JSON")
    rep_parser.set_defaults(func=cmd_reputation)
    
    # Leaderboard command
    lb_parser = subparsers.add_parser("leaderboard", help="Get reputation leaderboard")
    lb_parser.add_argument("--limit", type=int, default=10, help="Number of entries")
    lb_parser.add_argument("--tier", help="Filter by tier")
    lb_parser.add_argument("--db", default="reputation.db", help="Database path")
    lb_parser.add_argument("--json", action="store_true", help="Output as JSON")
    lb_parser.set_defaults(func=cmd_leaderboard)
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Get global statistics")
    stats_parser.add_argument("--db", default="reputation.db", help="Database path")
    stats_parser.add_argument("--json", action="store_true", help="Output as JSON")
    stats_parser.set_defaults(func=cmd_stats)
    
    # Projection command
    proj_parser = subparsers.add_parser("projection", help="Get reputation projection")
    proj_parser.add_argument("miner_id", help="Miner ID to query")
    proj_parser.add_argument("--epochs", type=int, default=100, help="Epochs to project")
    proj_parser.add_argument("--db", default="reputation.db", help="Database path")
    proj_parser.add_argument("--json", action="store_true", help="Output as JSON")
    proj_parser.set_defaults(func=cmd_projection)
    
    # Calculate command
    calc_parser = subparsers.add_parser("calculate", help="Calculate reputation metrics")
    calc_parser.add_argument("--rp", type=int, default=0, help="Total RP")
    calc_parser.add_argument("--epochs", type=int, default=0, help="Epochs participated")
    calc_parser.add_argument("--json", action="store_true", help="Output as JSON")
    calc_parser.set_defaults(func=cmd_calculate)
    
    return parser


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        print("\nExamples:")
        print("  rustchain reputation RTC_vintage_g4_001")
        print("  rustchain leaderboard --limit 5")
        print("  rustchain stats")
        print("  rustchain projection RTC_miner --epochs 500")
        print("  rustchain calculate --rp 150 --epochs 75")
        return 0
    
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
