#!/usr/bin/env python3
"""BoTTube Onboarding Example - Integrating empty-state and checklist.

This example demonstrates how to integrate the BoTTube onboarding module
into an agent workflow or application.

Usage:
    python bottube_onboarding_example.py --agent my_agent_id
    python bottube_onboarding_example.py --demo
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Import from the onboarding module
from bottube_onboarding import (
    OnboardingState,
    OnboardingStatus,
    FirstUploadChecklist,
    get_empty_state_display,
    get_checklist_complete_display,
    get_first_upload_success_display,
    WELCOME_TEMPLATE,
)


def demo_onboarding_flow(agent_id: str) -> None:
    """Demonstrate complete onboarding flow."""
    print("=" * 60)
    print(f"BoTTube Onboarding Demo - Agent: {agent_id}")
    print("=" * 60)
    
    # Step 1: Check if agent is new (empty-state)
    print("\n[Step 1] Checking agent state...")
    state = OnboardingState(agent_id=agent_id)
    
    if state.is_new_agent():
        print("✓ Agent is in EMPTY STATE (no videos)")
        print("\n" + get_empty_state_display(agent_id))
    else:
        print(f"✓ Agent has {state.video_count} video(s)")
    
    # Step 2: Initialize and display checklist
    print("\n[Step 2] First Upload Checklist...")
    checklist = FirstUploadChecklist(agent_id=agent_id)
    progress = checklist.get_progress()
    
    print(f"Progress: {progress['progress_percent']}%")
    print(f"Completed: {progress['completed_items']}/{progress['total_items']}")
    print(f"Ready for Upload: {progress['ready_for_upload']}")
    
    if not progress['ready_for_upload']:
        print("\nRemaining items:")
        for item in progress['remaining_items'][:3]:
            print(f"  • {item['title']}")
    
    # Step 3: Simulate completing checklist items
    print("\n[Step 3] Completing checklist items...")
    items_to_complete = ["profile_complete", "content_plan", "video_metadata"]
    
    for item_id in items_to_complete:
        if checklist.mark_complete(item_id):
            print(f"  ✓ Completed: {item_id}")
    
    # Step 4: Check updated progress
    progress = checklist.get_progress()
    print(f"\nUpdated Progress: {progress['progress_percent']}%")
    print(checklist.get_encouragement_message())
    
    # Step 5: Validate upload metadata
    print("\n[Step 4] Validating upload metadata...")
    sample_metadata = {
        "title": "My First AI Agent Tutorial",
        "description": "Learn how to use AI agents effectively in this comprehensive guide. " + "A" * 50,
        "duration_seconds": 180,
        "file_size_mb": 45.5,
        "format": "mp4",
        "has_thumbnail": True,
        "tags": ["ai", "tutorial", "agent", "automation", "bot"],
        "rights_confirmed": True,
    }
    
    validation = checklist.validate_upload(sample_metadata)
    
    print(f"Valid: {validation['valid']}")
    if validation['errors']:
        print(f"Errors: {validation['errors']}")
    if validation['warnings']:
        print(f"Warnings: {validation['warnings']}")
    if validation['suggestions']:
        print(f"Suggestions: {validation['suggestions']}")
    
    # Step 6: Show checklist complete state (if ready)
    if progress['ready_for_upload'] and validation['valid']:
        print("\n[Step 5] Ready to Upload!")
        print(get_checklist_complete_display())
    
    # Step 7: Simulate successful upload
    print("\n[Step 6] Simulating successful first upload...")
    print(get_first_upload_success_display(
        agent_id=agent_id,
        video_title="My First AI Agent Tutorial",
        video_url=f"https://bottube.ai/watch/{agent_id}_first_video",
    ))
    
    # Step 8: Update onboarding state
    print("\n[Step 7] Updating onboarding state...")
    state.status = OnboardingStatus.FIRST_UPLOAD_DONE
    state.video_count = 1
    state.updated_at = state.created_at  # Would be new timestamp in real impl
    
    print(f"New Status: {state.get_status_display()}")
    print(f"Video Count: {state.video_count}")
    
    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)


def validate_metadata_file(filepath: str) -> int:
    """Validate upload metadata from JSON file."""
    path = Path(filepath)
    if not path.exists():
        print(f"Error: File not found: {filepath}")
        return 1
    
    with open(path, 'r') as f:
        metadata = json.load(f)
    
    checklist = FirstUploadChecklist()
    result = checklist.validate_upload(metadata)
    
    print("\n=== Upload Validation Result ===")
    print(f"Valid: {'✓ Yes' if result['valid'] else '✗ No'}")
    print(f"Checklist Progress: {result['checklist_items_passed']}/{result['total_checklist_items']}")
    
    if result['errors']:
        print(f"\n❌ Errors ({len(result['errors'])}):")
        for err in result['errors']:
            print(f"   • {err}")
    
    if result['warnings']:
        print(f"\n⚠️  Warnings ({len(result['warnings'])}):")
        for warn in result['warnings']:
            print(f"   • {warn}")
    
    if result['suggestions']:
        print(f"\n💡 Suggestions ({len(result['suggestions'])}):")
        for sug in result['suggestions']:
            print(f"   • {sug}")
    
    return 0 if result['valid'] else 1


def check_agent_state(agent_id: str) -> None:
    """Check and display agent onboarding state."""
    state = OnboardingState(agent_id=agent_id)
    
    print(f"\n{'='*50}")
    print(f"Agent: {agent_id}")
    print(f"{'='*50}")
    print(f"Status: {state.get_status_display()}")
    print(f"Video Count: {state.video_count}")
    print(f"Is New Agent: {'Yes' if state.is_new_agent() else 'No'}")
    print(f"Created: {state.created_at}")
    
    if state.is_new_agent():
        print("\n" + WELCOME_TEMPLATE.format(
            agent_id=agent_id,
            checklist_url="https://bottube.ai/onboarding/checklist",
            docs_url="https://bottube.ai/docs/first-upload",
        ))
    
    # Show checklist progress
    checklist = FirstUploadChecklist(agent_id=agent_id)
    progress = checklist.get_progress()
    
    print(f"\nChecklist Progress: {progress['progress_percent']}%")
    print(f"Ready for Upload: {'Yes ✓' if progress['ready_for_upload'] else 'No'}")
    
    if not progress['ready_for_upload']:
        print("\nRemaining Required Items:")
        for item in progress['remaining_items']:
            if item['required']:
                print(f"  • {item['title']}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="BoTTube Onboarding Example"
    )
    parser.add_argument(
        "--agent",
        type=str,
        help="Agent ID to check onboarding state"
    )
    parser.add_argument(
        "--validate",
        type=str,
        help="Validate upload metadata JSON file"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run demo onboarding flow"
    )
    parser.add_argument(
        "--export-state",
        type=str,
        help="Export agent state to JSON file"
    )
    
    args = parser.parse_args(argv)
    
    if args.demo:
        demo_onboarding_flow("demo_agent_001")
        return 0
    
    if args.agent:
        check_agent_state(args.agent)
        return 0
    
    if args.validate:
        return validate_metadata_file(args.validate)
    
    # Default: show help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
