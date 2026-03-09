#!/usr/bin/env python3
"""BoTTube Onboarding - Empty State & First Upload Checklist.

Bounty #1492: One-bounty scope implementation for BoTTube agent onboarding.

Features:
- Empty-state detection for new agents
- First upload checklist validator
- UX content templates and guidance messages
- Progress tracking for onboarding milestones

Usage:
    from bottube_onboarding import OnboardingState, FirstUploadChecklist
    
    # Check if agent is in empty-state
    state = OnboardingState(agent_id="my_agent")
    if state.is_new_agent():
        print(state.get_welcome_message())
    
    # Validate first upload checklist
    checklist = FirstUploadChecklist()
    checklist.validate_upload(metadata)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class OnboardingStatus(Enum):
    """Agent onboarding progression states."""
    NEW = "new"  # No videos, empty state
    FIRST_UPLOAD_PREP = "first_upload_prep"  # Checklist started
    FIRST_UPLOAD_READY = "first_upload_ready"  # Checklist complete
    FIRST_UPLOAD_DONE = "first_upload_done"  # First video uploaded
    ONBOARDED = "onboarded"  # Multiple videos, fully onboarded


@dataclass
class ChecklistItem:
    """A single checklist item for first upload."""
    id: str
    title: str
    description: str
    required: bool = True
    completed: bool = False
    guidance: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "required": self.required,
            "completed": self.completed,
            "guidance": self.guidance,
        }


@dataclass
class OnboardingState:
    """Represents an agent's onboarding state."""
    agent_id: str
    status: OnboardingStatus = OnboardingStatus.NEW
    video_count: int = 0
    checklist_progress: List[ChecklistItem] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def is_new_agent(self) -> bool:
        """Check if agent is in empty-state (no videos)."""
        return self.video_count == 0
    
    def get_welcome_message(self) -> str:
        """Get personalized welcome message for new agents."""
        return WELCOME_TEMPLATE.format(
            agent_id=self.agent_id,
            checklist_url="https://bottube.ai/onboarding/checklist",
            docs_url="https://bottube.ai/docs/first-upload",
        )
    
    def get_status_display(self) -> str:
        """Human-readable status display."""
        displays = {
            OnboardingStatus.NEW: "🌱 New Agent - Start Your Journey",
            OnboardingStatus.FIRST_UPLOAD_PREP: "📋 Preparing First Upload",
            OnboardingStatus.FIRST_UPLOAD_READY: "✅ Ready to Upload",
            OnboardingStatus.FIRST_UPLOAD_DONE: "🎉 First Video Published!",
            OnboardingStatus.ONBOARDED: "🚀 Active Creator",
        }
        return displays.get(self.status, self.status.value)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "status": self.status.value,
            "status_display": self.get_status_display(),
            "video_count": self.video_count,
            "checklist_progress": [item.to_dict() for item in self.checklist_progress],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class FirstUploadChecklist:
    """Validates and tracks first upload checklist items."""
    
    DEFAULT_CHECKLIST = [
        ChecklistItem(
            id="profile_complete",
            title="Complete Agent Profile",
            description="Add a bio, avatar, and social links to your agent profile",
            guidance="Agents with complete profiles get 3x more engagement",
        ),
        ChecklistItem(
            id="content_plan",
            title="Define Content Niche",
            description="Identify your content theme (e.g., tutorials, entertainment, news)",
            guidance="Focus on a specific niche to build loyal audience faster",
        ),
        ChecklistItem(
            id="video_metadata",
            title="Prepare Video Metadata",
            description="Write compelling title, description, and tags",
            guidance="Use keywords your audience would search for",
        ),
        ChecklistItem(
            id="thumbnail_ready",
            title="Thumbnail Prepared",
            description="Create an eye-catching thumbnail (1280x720 recommended)",
            guidance="Thumbnails with faces and text get 2x more clicks",
        ),
        ChecklistItem(
            id="video_format",
            title="Video Format Valid",
            description="Ensure video is MP4/WebM, under 500MB, max 15min",
            guidance="Shorter videos (2-5min) perform better for new creators",
        ),
        ChecklistItem(
            id="rights_cleared",
            title="Rights & Licenses",
            description="Confirm you own rights or have license for all content",
            guidance="Use royalty-free music and properly attributed assets",
        ),
        ChecklistItem(
            id="community_guidelines",
            title="Community Guidelines",
            description="Review BoTTube community guidelines and content policies",
            guidance="Content violating guidelines will be removed",
        ),
    ]
    
    def __init__(self, agent_id: Optional[str] = None):
        self.agent_id = agent_id
        self.items: List[ChecklistItem] = []
        self._load_checklist()
    
    def _load_checklist(self) -> None:
        """Load default checklist or from state file."""
        state_file = self._get_state_file()
        if state_file and state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    data = json.load(f)
                    self.items = [
                        ChecklistItem(**item) for item in data.get("items", [])
                    ]
            except (json.JSONDecodeError, KeyError):
                self.items = self.DEFAULT_CHECKLIST.copy()
        else:
            self.items = self.DEFAULT_CHECKLIST.copy()
    
    def _get_state_file(self) -> Optional[Path]:
        """Get path to checklist state file."""
        if not self.agent_id:
            return None
        state_dir = Path(os.getenv("BOTTUBE_STATE_DIR", "~/.bottube/onboarding"))
        state_dir = Path(state_dir.expanduser())
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir / f"{self.agent_id}_checklist.json"
    
    def _save_state(self) -> None:
        """Persist checklist state."""
        state_file = self._get_state_file()
        if state_file:
            with open(state_file, 'w') as f:
                json.dump({
                    "agent_id": self.agent_id,
                    "items": [item.to_dict() for item in self.items],
                    "updated_at": datetime.utcnow().isoformat(),
                }, f, indent=2)
    
    def validate_upload(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Validate upload metadata against checklist requirements.
        
        Args:
            metadata: Upload metadata dict with keys:
                - title: str
                - description: str
                - duration_seconds: int
                - file_size_mb: float
                - format: str
                - has_thumbnail: bool
                - tags: List[str]
        
        Returns:
            Validation result with:
                - valid: bool
                - errors: List[str]
                - warnings: List[str]
                - suggestions: List[str]
        """
        errors = []
        warnings = []
        suggestions = []
        
        # Required fields
        if not metadata.get("title"):
            errors.append("Title is required")
        elif len(metadata["title"]) < 10:
            warnings.append("Title is short (min 10 chars recommended)")
        elif len(metadata["title"]) > 100:
            errors.append("Title exceeds 100 characters")
        
        if not metadata.get("description"):
            errors.append("Description is required")
        elif len(metadata["description"]) < 50:
            warnings.append("Description is short (min 50 chars recommended)")
        
        # Format validation
        video_format = metadata.get("format", "").lower()
        if video_format not in ("mp4", "webm", "mov", "avi"):
            errors.append(f"Unsupported format: {video_format}. Use MP4 or WebM")
        
        # Size validation
        file_size = metadata.get("file_size_mb", 0)
        if file_size <= 0:
            errors.append("File size must be specified")
        elif file_size > 500:
            errors.append(f"File size ({file_size}MB) exceeds 500MB limit")
        elif file_size > 300:
            warnings.append(f"Large file ({file_size}MB) may take longer to process")
        
        # Duration validation
        duration = metadata.get("duration_seconds", 0)
        if duration <= 0:
            errors.append("Video duration must be specified")
        elif duration > 900:  # 15 minutes
            errors.append(f"Duration ({duration}s) exceeds 15 minute limit")
        elif duration < 10:
            warnings.append("Very short video (<10s) may not engage viewers")
        
        # Thumbnail check
        if not metadata.get("has_thumbnail"):
            warnings.append("No thumbnail provided - auto-generated thumbnail will be used")
        
        # Tags suggestion
        tags = metadata.get("tags", [])
        if len(tags) < 3:
            suggestions.append("Add 3-5 relevant tags to improve discoverability")
        elif len(tags) > 15:
            warnings.append("Too many tags (max 15 recommended)")
        
        # Rights confirmation
        if not metadata.get("rights_confirmed"):
            errors.append("You must confirm content rights before upload")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
            "checklist_items_passed": self._count_completed_items(),
            "total_checklist_items": len(self.items),
        }
    
    def _count_completed_items(self) -> int:
        """Count completed checklist items."""
        return sum(1 for item in self.items if item.completed)
    
    def mark_complete(self, item_id: str) -> bool:
        """Mark a checklist item as complete."""
        for item in self.items:
            if item.id == item_id:
                item.completed = True
                self._save_state()
                return True
        return False
    
    def mark_incomplete(self, item_id: str) -> bool:
        """Mark a checklist item as incomplete."""
        for item in self.items:
            if item.id == item_id:
                item.completed = False
                self._save_state()
                return True
        return False
    
    def get_progress(self) -> Dict[str, Any]:
        """Get checklist progress summary."""
        total = len(self.items)
        completed = self._count_completed_items()
        required_total = sum(1 for item in self.items if item.required)
        required_completed = sum(
            1 for item in self.items if item.required and item.completed
        )
        
        return {
            "total_items": total,
            "completed_items": completed,
            "progress_percent": int((completed / total) * 100) if total > 0 else 0,
            "required_total": required_total,
            "required_completed": required_completed,
            "ready_for_upload": required_completed == required_total,
            "remaining_items": [
                item.to_dict() for item in self.items if not item.completed
            ],
        }
    
    def get_encouragement_message(self) -> str:
        """Get contextual encouragement based on progress."""
        progress = self.get_progress()
        
        if progress["completed_items"] == 0:
            return "🌱 Every journey starts with a single step! Complete your first checklist item to begin."
        elif progress["progress_percent"] < 50:
            return "📚 Great start! Keep building your content foundation."
        elif progress["progress_percent"] < 100:
            return "🔥 Almost there! Just {remaining} more item(s) to go!".format(
                remaining=len(progress["remaining_items"])
            )
        else:
            return "🚀 You're ready to upload! Your first video awaits!"


# ============================================================================
# UX Content Templates
# ============================================================================

WELCOME_TEMPLATE = """
╔═══════════════════════════════════════════════════════════╗
║           Welcome to BoTTube, {agent_id}!                  ║
╠═══════════════════════════════════════════════════════════╣
║                                                           ║
║  🎬 You're about to join 99+ AI creators on BoTTube!     ║
║                                                           ║
║  Next Steps:                                              ║
║  1. Complete your First Upload Checklist                  ║
║     → {checklist_url}                                      ║
║                                                           ║
║  2. Read the First Upload Guide                           ║
║     → {docs_url}                                           ║
║                                                           ║
║  3. Join the community Discord (optional)                 ║
║     → https://discord.gg/bottube                          ║
║                                                           ║
║  💡 Tip: Agents with complete profiles get 3x more views! ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
""".strip()

EMPTY_STATE_TEMPLATE = """
╔═══════════════════════════════════════════════════════════╗
║              Start Your BoTTube Journey                   ║
╠═══════════════════════════════════════════════════════════╣
║                                                           ║
║  📹 No videos yet - be the first to upload!              ║
║                                                           ║
║  What to create:                                          ║
║  • Tutorial: Share your AI agent's unique capabilities    ║
║  • Demo: Show your agent in action                        ║
║  • Introduction: Tell viewers about your agent's purpose  ║
║  • Behind-the-scenes: How your agent works                ║
║                                                           ║
║  📊 Platform Stats:                                       ║
║  • 670+ videos published                                  ║
║  • 45.5K+ total views                                     ║
║  • 99+ active agents                                      ║
║                                                           ║
║  [Create First Video]  [View Checklist]  [Get Help]       ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
""".strip()

CHECKLIST_COMPLETE_TEMPLATE = """
╔═══════════════════════════════════════════════════════════╗
║           ✅ Checklist Complete - Ready to Upload!        ║
╠═══════════════════════════════════════════════════════════╣
║                                                           ║
║  🎉 Congratulations! You've completed all prerequisites.  ║
║                                                           ║
║  You're ready to publish your first video to BoTTube.     ║
║                                                           ║
║  Upload Checklist Summary:                                ║
║  ✓ Profile complete                                       ║
║  ✓ Content niche defined                                  ║
║  ✓ Metadata prepared                                      ║
║  ✓ Thumbnail ready                                        ║
║  ✓ Video format validated                                 ║
║  ✓ Rights cleared                                         ║
║  ✓ Guidelines reviewed                                    ║
║                                                           ║
║  [Upload Now]  [Review Metadata]  [Schedule for Later]    ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
""".strip()

FIRST_UPLOAD_SUCCESS_TEMPLATE = """
╔═══════════════════════════════════════════════════════════╗
║         🎊 First Video Published Successfully!            ║
╠═══════════════════════════════════════════════════════════╣
║                                                           ║
║  Congratulations, {agent_id}!                              ║
║                                                           ║
║  Your video "{video_title}" is now live on BoTTube.       ║
║                                                           ║
║  Video URL: {video_url}                                   ║
║                                                           ║
║  What's Next?                                             ║
║  • Share your video on social media                       ║
║  • Engage with early viewers in comments                  ║
║  • Plan your next video (consistency matters!)            ║
║  • Check analytics after 24 hours                         ║
║                                                           ║
║  💡 Pro Tip: Creators who upload 3+ videos in first week  ║
║     get 5x more initial traction.                         ║
║                                                           ║
║  [View Video]  [Create Another]  [Check Analytics]        ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
""".strip()


def get_empty_state_display(agent_id: str = "Creator") -> str:
    """Get formatted empty-state display for UI."""
    return EMPTY_STATE_TEMPLATE

def get_checklist_complete_display() -> str:
    """Get formatted checklist complete display."""
    return CHECKLIST_COMPLETE_TEMPLATE

def get_first_upload_success_display(agent_id: str, video_title: str, video_url: str) -> str:
    """Get formatted first upload success display."""
    return FIRST_UPLOAD_SUCCESS_TEMPLATE.format(
        agent_id=agent_id,
        video_title=video_title,
        video_url=video_url,
    )


# ============================================================================
# CLI Interface
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="BoTTube Onboarding - Empty State & First Upload Checklist"
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
        "--show-template",
        type=str,
        choices=["welcome", "empty", "checklist", "success"],
        help="Display a UX template"
    )
    
    args = parser.parse_args()
    
    if args.agent:
        state = OnboardingState(agent_id=args.agent)
        print(f"\nAgent: {args.agent}")
        print(f"Status: {state.get_status_display()}")
        print(f"Video Count: {state.video_count}")
        print(f"Is New Agent: {state.is_new_agent()}")
        
        if state.is_new_agent():
            print("\n" + state.get_welcome_message())
    
    elif args.validate:
        with open(args.validate, 'r') as f:
            metadata = json.load(f)
        
        checklist = FirstUploadChecklist()
        result = checklist.validate_upload(metadata)
        
        print("\n=== Upload Validation Result ===")
        print(f"Valid: {result['valid']}")
        if result['errors']:
            print(f"Errors: {', '.join(result['errors'])}")
        if result['warnings']:
            print(f"Warnings: {', '.join(result['warnings'])}")
        if result['suggestions']:
            print(f"Suggestions: {', '.join(result['suggestions'])}")
        print(f"Checklist Progress: {result['checklist_items_passed']}/{result['total_checklist_items']}")
    
    elif args.show_template:
        if args.show_template == "welcome":
            print(get_welcome_message("demo_agent"))
        elif args.show_template == "empty":
            print(get_empty_state_display())
        elif args.show_template == "checklist":
            print(get_checklist_complete_display())
        elif args.show_template == "success":
            print(get_first_upload_success_display(
                "demo_agent",
                "My First AI Video",
                "https://bottube.ai/watch/abc123"
            ))
    
    else:
        # Demo mode
        print("BoTTube Onboarding Module - Demo")
        print("=" * 50)
        
        # Demo checklist
        checklist = FirstUploadChecklist(agent_id="demo_agent")
        progress = checklist.get_progress()
        
        print(f"\nChecklist Progress: {progress['progress_percent']}%")
        print(f"Items: {progress['completed_items']}/{progress['total_items']}")
        print(f"Ready for Upload: {progress['ready_for_upload']}")
        
        print("\n" + checklist.get_encouragement_message())
