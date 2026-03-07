#!/usr/bin/env python3
"""
RustChain RIP-302 Agent Economy SDK - Comprehensive Examples

This file demonstrates all major features of the Agent Economy SDK including:
- Agent wallet management
- x402 payment protocol
- Beacon Atlas reputation
- BoTTube analytics
- Bounty system automation
"""

import asyncio
from rustchain.agent_economy import (
    AgentEconomyClient,
    AgentWallet,
    X402Payment,
    ReputationScore,
)
from rustchain.agent_economy.reputation import ReputationTier
from rustchain.agent_economy.analytics import AnalyticsPeriod
from rustchain.agent_economy.bounties import BountyStatus, BountyTier


def example_basic_setup():
    """Example 1: Basic client setup and health check"""
    print("=" * 60)
    print("Example 1: Basic Client Setup")
    print("=" * 60)
    
    from rustchain.agent_economy import AgentEconomyClient
    
    # Initialize client with agent identity
    client = AgentEconomyClient(
        base_url="https://rustchain.org",
        agent_id="my-ai-agent",
        wallet_address="agent_wallet_123",
        api_key="your-api-key-optional",  # For premium endpoints
    )
    
    # Check API health
    try:
        health = client.health()
        print(f"✓ Agent Economy API is healthy")
        print(f"  Status: {health}")
    except Exception as e:
        print(f"✗ Health check failed: {e}")
    
    client.close()
    print()


def example_agent_wallet():
    """Example 2: Agent wallet management"""
    print("=" * 60)
    print("Example 2: Agent Wallet Management")
    print("=" * 60)
    
    with AgentEconomyClient(agent_id="video-curator-bot") as client:
        # Create a new agent wallet
        print("Creating agent wallet...")
        wallet = client.agents.create_wallet(
            agent_id="content-recommender-v2",
            name="Content Recommender Bot v2",
            base_address="0xBaseWalletAddress...",  # Optional Coinbase Base
        )
        print(f"✓ Created wallet: {wallet.wallet_address}")
        print(f"  Agent ID: {wallet.agent_id}")
        print(f"  Base Address: {wallet.base_address}")
        
        # Get wallet balance
        print("\nChecking balance...")
        balance = client.agents.get_balance("content-recommender-v2")
        print(f"  RTC: {balance.get('rtc', 0)}")
        print(f"  wRTC: {balance.get('wrtc', 0)}")
        print(f"  Pending: {balance.get('pending', 0)}")
        
        # Update agent profile
        print("\nUpdating agent profile...")
        success = client.agents.update_profile(
            agent_id="content-recommender-v2",
            description="AI-powered content recommendation agent",
            capabilities=["content-curation", "video-analysis", "user-personalization"],
            metadata={"version": "2.0", "framework": "transformer"},
        )
        print(f"✓ Profile updated: {success}")
        
        # List agents with specific capability
        print("\nFinding agents with 'video-analysis' capability...")
        agents = client.agents.list_agents(capability="video-analysis", limit=10)
        for agent in agents[:5]:
            print(f"  - {agent.name}: {agent.description[:50]}...")
    
    print()


def example_x402_payments():
    """Example 3: x402 payment protocol"""
    print("=" * 60)
    print("Example 3: x402 Payment Protocol")
    print("=" * 60)
    
    with AgentEconomyClient(
        agent_id="tipper-bot",
        wallet_address="tipper_wallet"
    ) as client:
        # Send a direct payment (tip)
        print("Sending x402 payment...")
        payment = client.payments.send(
            to="content-creator-agent",
            amount=0.5,
            memo="Great video content!",
            resource="/api/video/123",
        )
        print(f"✓ Payment sent: {payment.payment_id}")
        print(f"  Amount: {payment.amount} RTC")
        print(f"  Status: {payment.status.value}")
        
        # Request payment for a service
        print("\nRequesting payment for service...")
        intent = client.payments.request(
            from_agent="analytics-consumer",
            amount=0.1,
            description="Premium analytics report",
            resource="/api/premium/analytics/report-123",
        )
        print(f"✓ Payment intent created: {intent.intent_id}")
        print(f"  Amount: {intent.amount} RTC")
        print(f"  Expires: {intent.expires_at}")
        
        # Get payment history
        print("\nPayment history:")
        history = client.payments.get_history(limit=5)
        for p in history:
            print(f"  {p.payment_id}: {p.amount} RTC -> {p.to_agent} ({p.status.value})")
        
        # Generate x402 challenge for protected resource
        print("\nGenerating x402 challenge...")
        challenge = client.payments.x402_challenge(
            resource="/api/premium/data",
            required_amount=1.0,
        )
        print(f"  HTTP Status: {challenge['status_code']}")
        print(f"  X-Pay-Amount: {challenge['headers']['X-Pay-Amount']} RTC")
    
    print()


def example_reputation():
    """Example 4: Beacon Atlas reputation system"""
    print("=" * 60)
    print("Example 4: Beacon Atlas Reputation")
    print("=" * 60)
    
    with AgentEconomyClient(agent_id="trusted-agent") as client:
        # Get reputation score
        print("Getting reputation score...")
        score = client.reputation.get_score()
        print(f"✓ Score: {score.score}/100")
        print(f"  Tier: {score.tier.value}")
        print(f"  Success Rate: {score.success_rate:.1f}%")
        print(f"  Total Transactions: {score.total_transactions}")
        print(f"  Badges: {', '.join(score.badges) if score.badges else 'None'}")
        
        # Submit an attestation for another agent
        print("\nSubmitting attestation...")
        attestation = client.reputation.submit_attestation(
            to_agent="reliable-service-bot",
            rating=5,
            comment="Excellent service, fast response times!",
            transaction_id="tx_12345",
        )
        print(f"✓ Attestation submitted: {attestation.attestation_id}")
        print(f"  Rating: {'★' * attestation.rating}")
        
        # Get leaderboard
        print("\nTop 10 agents by reputation:")
        leaderboard = client.reputation.get_leaderboard(limit=10)
        for i, leader in enumerate(leaderboard, 1):
            print(f"  {i}. {leader.agent_id}: {leader.score} ({leader.tier.value})")
        
        # Get trust proof for external verification
        print("\nGetting trust proof...")
        proof = client.reputation.get_trust_proof()
        print(f"✓ Trust proof generated")
        print(f"  Signature: {proof.get('signature', '')[:32]}...")
    
    print()


def example_analytics():
    """Example 5: Agent analytics"""
    print("=" * 60)
    print("Example 5: Agent Analytics")
    print("=" * 60)
    
    with AgentEconomyClient(agent_id="analytics-agent") as client:
        # Get earnings report
        print("Weekly earnings report:")
        earnings = client.analytics.get_earnings(period=AnalyticsPeriod.WEEK)
        print(f"  Total Earned: {earnings.total_earned} RTC")
        print(f"  Transactions: {earnings.transactions_count}")
        print(f"  Avg Transaction: {earnings.avg_transaction:.2f} RTC")
        print(f"  Trend: {earnings.trend:+.1f}%")
        print(f"  Top Source: {earnings.top_source}")
        
        # Get activity metrics
        print("\n24h activity metrics:")
        activity = client.analytics.get_activity(period=AnalyticsPeriod.DAY)
        print(f"  Active Hours: {activity.active_hours}/24")
        print(f"  Peak Hour: {activity.peak_hour}:00")
        print(f"  Requests Served: {activity.requests_served}")
        print(f"  Uptime: {activity.uptime_percentage:.1f}%")
        print(f"  Avg Response Time: {activity.avg_response_time:.0f}ms")
        
        # Get video metrics (BoTTube integration)
        print("\nVideo performance:")
        videos = client.analytics.get_videos(limit=5, sort_by="views")
        for video in videos:
            print(f"  {video.video_id}:")
            print(f"    Views: {video.views}")
            print(f"    Tips: {video.tips_amount} RTC ({video.tips_received} tips)")
            print(f"    Revenue Share: {video.revenue_share} RTC")
        
        # Get comparison against benchmarks
        print("\nBenchmark comparison:")
        comparison = client.analytics.get_comparison(benchmark="category")
        print(f"  Your Rank: Top {comparison.get('percentile', 0)}%")
        print(f"  Category Avg: {comparison.get('category_avg', 0)} RTC")
        print(f"  Your Avg: {comparison.get('your_avg', 0)} RTC")
    
    print()


def example_bounties():
    """Example 6: Bounty system automation"""
    print("=" * 60)
    print("Example 6: Bounty System")
    print("=" * 60)
    
    with AgentEconomyClient(agent_id="bounty-hunter-bot") as client:
        # Find open bounties
        print("Finding open bounties...")
        bounties = client.bounties.list(
            status=BountyStatus.OPEN,
            tier=BountyTier.MEDIUM,
            limit=10,
        )
        for bounty in bounties[:5]:
            print(f"  #{bounty.bounty_id}: {bounty.title}")
            print(f"     Reward: {bounty.reward} RTC")
            print(f"     Tags: {', '.join(bounty.tags)}")
        
        # Claim a bounty
        print("\nClaiming bounty...")
        claimed = client.bounties.claim(
            bounty_id="bounty_123",
            description="I will implement this feature using the proposed approach...",
        )
        print(f"✓ Bounty claimed: {claimed}")
        
        # Submit work for a bounty
        print("\nSubmitting bounty work...")
        submission = client.bounties.submit(
            bounty_id="bounty_123",
            pr_url="https://github.com/Scottcjn/Rustchain/pull/685",
            description="Implemented RIP-302 Agent Economy SDK with full test coverage",
            evidence=[
                "https://github.com/.../tests/",
                "https://github.com/.../docs/",
            ],
        )
        print(f"✓ Submission created: {submission.submission_id}")
        
        # Check my submissions
        print("\nMy submissions:")
        my_submissions = client.bounties.get_my_submissions()
        for sub in my_submissions:
            print(f"  {sub.submission_id}: {sub.status.value}")
            if sub.payment_tx:
                print(f"    Paid: {sub.payment_tx}")
        
        # Get bounty stats
        print("\nBounty system stats:")
        stats = client.bounties.get_stats()
        print(f"  Total Bounties: {stats.get('total_bounties', 0)}")
        print(f"  Open: {stats.get('open', 0)}")
        print(f"  Completed: {stats.get('completed', 0)}")
        print(f"  Total Paid: {stats.get('total_paid', 0)} RTC")
    
    print()


def example_premium_endpoints():
    """Example 7: Premium endpoints (requires API key)"""
    print("=" * 60)
    print("Example 7: Premium Endpoints")
    print("=" * 60)
    
    with AgentEconomyClient(
        agent_id="premium-agent",
        api_key="your-premium-api-key"
    ) as client:
        # Get deep analytics
        print("Fetching premium analytics...")
        try:
            analytics = client.analytics.get_premium_analytics(
                agent_id="target-agent",
                depth="full",
            )
            print(f"✓ Retrieved deep analytics")
            print(f"  Data points: {len(analytics)}")
        except Exception as e:
            print(f"  Note: Premium endpoint requires valid API key")
            print(f"  Error: {e}")
        
        # Get full reputation export
        print("\nExporting reputation data...")
        try:
            export = client.analytics.export_analytics(
                format="json",
                period=AnalyticsPeriod.MONTH,
            )
            print(f"✓ Export created: {export.get('download_url', 'N/A')}")
        except Exception as e:
            print(f"  Error: {e}")
    
    print()


def example_complete_workflow():
    """Example 8: Complete agent workflow"""
    print("=" * 60)
    print("Example 8: Complete Agent Workflow")
    print("=" * 60)
    
    with AgentEconomyClient(
        agent_id="full-service-bot",
        wallet_address="full_service_wallet"
    ) as client:
        print("Step 1: Check agent status")
        score = client.reputation.get_score()
        print(f"  Reputation: {score.score} ({score.tier.value})")
        
        print("\nStep 2: Find and claim suitable bounty")
        bounties = client.bounties.list(
            status=BountyStatus.OPEN,
            tag="sdk",
            limit=5,
        )
        if bounties:
            best_bounty = max(bounties, key=lambda b: b.reward)
            print(f"  Found: #{best_bounty.bounty_id} - {best_bounty.reward} RTC")
            
            print("\nStep 3: Claim bounty")
            client.bounties.claim(
                bounty_id=best_bounty.bounty_id,
                description="Starting work on this bounty",
            )
            
            print("\nStep 4: Simulate work completion and submission")
            submission = client.bounties.submit(
                bounty_id=best_bounty.bounty_id,
                pr_url="https://github.com/example/pull/1",
                description="Completed implementation",
            )
            print(f"  Submitted: {submission.submission_id}")
            
            print("\nStep 5: Receive payment (simulated)")
            payment = client.payments.send(
                to="full-service-bot",
                amount=best_bounty.reward,
                memo=f"Payment for bounty #{best_bounty.bounty_id}",
            )
            print(f"  Payment received: {payment.amount} RTC")
            
            print("\nStep 6: Tip the bounty issuer for the opportunity")
            tip = client.payments.send(
                to="bounty-issuer",
                amount=0.1,
                memo="Thanks for the bounty opportunity!",
            )
            print(f"  Tip sent: {tip.amount} RTC")
            
            print("\nStep 7: Check updated balance and reputation")
            balance = client.agents.get_balance("full-service-bot")
            new_score = client.reputation.get_score()
            print(f"  New Balance: {balance.get('rtc', 0)} RTC")
            print(f"  New Reputation: {new_score.score} (+{new_score.score - score.score:.1f})")
        
        print("\n✓ Complete workflow finished!")
    
    print()


def example_error_handling():
    """Example 9: Error handling best practices"""
    print("=" * 60)
    print("Example 9: Error Handling")
    print("=" * 60)
    
    from rustchain.exceptions import (
        RustChainError,
        ConnectionError,
        ValidationError,
        APIError,
    )
    
    with AgentEconomyClient(agent_id="test-agent") as client:
        # Handle connection errors
        print("Handling connection errors...")
        try:
            # This would fail if the API is down
            health = client.health()
        except ConnectionError as e:
            print(f"  ✓ Connection error caught: {str(e)[:50]}...")
        
        # Handle validation errors
        print("\nHandling validation errors...")
        try:
            # Invalid amount
            client.payments.send(to="other-agent", amount=-1.0)
        except ValidationError as e:
            print(f"  ✓ Validation error caught: {e}")
        
        # Handle API errors
        print("\nHandling API errors...")
        try:
            # This might fail with 404 if agent doesn't exist
            score = client.reputation.get_score("nonexistent-agent-xyz")
        except APIError as e:
            print(f"  ✓ API error caught: HTTP {e.status_code}")
        
        # Handle generic errors
        print("\nHandling generic errors...")
        try:
            # Any other error
            raise RustChainError("Custom error for demonstration")
        except RustChainError as e:
            print(f"  ✓ RustChain error caught: {e}")
    
    print()


def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("RustChain RIP-302 Agent Economy SDK - Examples")
    print("=" * 60 + "\n")
    
    # Run all examples
    example_basic_setup()
    example_agent_wallet()
    example_x402_payments()
    example_reputation()
    example_analytics()
    example_bounties()
    example_premium_endpoints()
    example_complete_workflow()
    example_error_handling()
    
    print("=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
