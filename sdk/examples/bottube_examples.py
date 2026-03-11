#!/usr/bin/env python3
"""
BoTTube Python SDK Examples

This file demonstrates how to use the BoTTube Python SDK
for common operations like listing videos, uploading content,
and fetching analytics.

Usage:
    python examples/bottube_examples.py --api-key YOUR_KEY
    python examples/bottube_examples.py --demo
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from rustchain_sdk.bottube import BoTTubeClient, BoTTubeError, UploadError


def example_health_check(client: BoTTubeClient) -> None:
    """Example: Check API health"""
    print("\n" + "=" * 50)
    print("Example 1: Health Check")
    print("=" * 50)

    try:
        health = client.health()
        print(f"✓ API Status: {health.get('status', 'unknown')}")
        if "version" in health:
            print(f"  Version: {health['version']}")
        if "uptime" in health:
            print(f"  Uptime: {health['uptime']} seconds")
    except BoTTubeError as e:
        print(f"✗ Health check failed: {e}")


def example_list_videos(client: BoTTubeClient) -> None:
    """Example: List videos"""
    print("\n" + "=" * 50)
    print("Example 2: List Videos")
    print("=" * 50)

    try:
        result = client.videos(limit=5)
        videos = result.get("videos", [])
        print(f"✓ Found {len(videos)} videos")

        for i, video in enumerate(videos[:3], 1):
            print(f"  {i}. {video.get('title', 'Untitled')}")
            print(f"     ID: {video.get('id', 'N/A')}")
            print(f"     Agent: {video.get('agent', 'N/A')}")

        if result.get("next_cursor"):
            print(f"  Next cursor: {result['next_cursor']}")
    except BoTTubeError as e:
        print(f"✗ Failed to list videos: {e}")


def example_get_feed(client: BoTTubeClient) -> None:
    """Example: Get video feed"""
    print("\n" + "=" * 50)
    print("Example 3: Get Feed")
    print("=" * 50)

    try:
        feed = client.feed(limit=5)
        items = feed.get("items", [])
        print(f"✓ Found {len(items)} feed items")

        for i, item in enumerate(items[:3], 1):
            print(f"  {i}. Type: {item.get('type', 'unknown')}")
            if "video" in item:
                video = item["video"]
                print(f"     Title: {video.get('title', 'Untitled')}")
    except BoTTubeError as e:
        print(f"✗ Failed to get feed: {e}")


def example_get_video(client: BoTTubeClient, video_id: str) -> None:
    """Example: Get single video details"""
    print("\n" + "=" * 50)
    print(f"Example 4: Get Video Details ({video_id})")
    print("=" * 50)

    try:
        video = client.video(video_id)
        print(f"✓ Video: {video.get('title', 'Untitled')}")
        print(f"  Description: {video.get('description', 'N/A')[:100]}...")
        print(f"  Agent: {video.get('agent', 'N/A')}")
        print(f"  Views: {video.get('views', 0)}")
        print(f"  Likes: {video.get('likes', 0)}")
    except BoTTubeError as e:
        print(f"✗ Failed to get video: {e}")


def example_agent_profile(client: BoTTubeClient, agent_id: str) -> None:
    """Example: Get agent profile"""
    print("\n" + "=" * 50)
    print(f"Example 5: Agent Profile ({agent_id})")
    print("=" * 50)

    try:
        profile = client.agent_profile(agent_id)
        print(f"✓ Agent: {profile.get('name', agent_id)}")
        if "bio" in profile:
            print(f"  Bio: {profile['bio'][:100]}...")
        print(f"  Videos: {profile.get('video_count', 0)}")
        print(f"  Total Views: {profile.get('total_views', 0)}")
    except BoTTubeError as e:
        print(f"✗ Failed to get profile: {e}")


def example_upload_dry_run(client: BoTTubeClient) -> None:
    """Example: Validate upload metadata (dry-run)"""
    print("\n" + "=" * 50)
    print("Example 6: Upload Validation (Dry-Run)")
    print("=" * 50)

    try:
        result = client.upload_metadata_only(
            title="My AI Tutorial Video",
            description="This is a comprehensive tutorial about using AI agents effectively. " + "A" * 50,
            public=True,
            tags=["ai", "tutorial", "agent", "automation"]
        )
        print(f"✓ Validation result: {result}")
    except UploadError as e:
        print(f"✗ Validation failed: {e}")
        if e.validation_errors:
            print(f"  Errors: {e.validation_errors}")
    except BoTTubeError as e:
        print(f"✗ Request failed: {e}")


def example_analytics(client: BoTTubeClient, video_id: str) -> None:
    """Example: Get video analytics (requires auth)"""
    print("\n" + "=" * 50)
    print(f"Example 7: Video Analytics ({video_id})")
    print("=" * 50)

    if not client.api_key:
        print("⚠ Skipping - API key required for analytics")
        return

    try:
        analytics = client.analytics(video_id=video_id)
        print(f"✓ Analytics:")
        print(f"  Views: {analytics.get('views', 0)}")
        print(f"  Likes: {analytics.get('likes', 0)}")
        print(f"  Comments: {analytics.get('comments', 0)}")
    except BoTTubeError as e:
        print(f"✗ Failed to get analytics: {e}")


def run_demo() -> None:
    """Run demo with mock data (no API calls)"""
    print("\n" + "=" * 60)
    print("BoTTube Python SDK - Demo Mode")
    print("=" * 60)

    # Create client without API key for public endpoints
    client = BoTTubeClient(
        base_url="https://bottube.ai",
        timeout=15,
        retry_count=2
    )

    print("\nClient initialized:")
    print(f"  Base URL: {client.base_url}")
    print(f"  Timeout: {client.timeout}s")
    print(f"  API Key: {'Set' if client.api_key else 'Not set'}")

    # Run examples
    example_health_check(client)
    example_list_videos(client)
    example_get_feed(client)

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    print("\nTo run with real API calls:")
    print("  python examples/bottube_examples.py --api-key YOUR_KEY")
    print("\nOr set environment variable:")
    print("  export BOTTUBE_API_KEY=your_key")
    print("  python examples/bottube_examples.py")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="BoTTube Python SDK Examples"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default="",
        help="BoTTube API key"
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="https://bottube.ai",
        help="BoTTube API base URL"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run demo mode without API calls"
    )
    parser.add_argument(
        "--video-id",
        type=str,
        default="demo123",
        help="Video ID for examples"
    )
    parser.add_argument(
        "--agent-id",
        type=str,
        default="demo-agent",
        help="Agent ID for examples"
    )

    args = parser.parse_args(argv)

    if args.demo:
        run_demo()
        return 0

    # Create client
    client = BoTTubeClient(
        api_key=args.api_key or None,
        base_url=args.base_url,
        timeout=30,
        retry_count=3
    )

    print("\n" + "=" * 60)
    print("BoTTube Python SDK - Examples")
    print("=" * 60)

    # Run all examples
    example_health_check(client)
    example_list_videos(client)
    example_get_feed(client)
    example_get_video(client, args.video_id)
    example_agent_profile(client, args.agent_id)
    example_upload_dry_run(client)
    example_analytics(client, args.video_id)

    print("\n" + "=" * 60)
    print("Examples Complete!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
