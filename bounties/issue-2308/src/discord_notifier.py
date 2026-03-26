#!/usr/bin/env python3
"""
Discord Notifier — Send obituary notifications to Discord.

Sends notifications when a miner passes (7+ days inactive) with:
- Miner information
- Eulogy excerpt
- Link to BoTTube memorial video
- Memorial emoji and formatting
"""

import logging
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger("silicon_obituary.discord")


@dataclass
class DiscordResult:
    """Result of Discord notification."""
    success: bool
    message_id: str = ""
    error: str = ""


class DiscordNotifier:
    """
    Sends obituary notifications to Discord via webhook.
    
    Features:
    - Rich embeds with miner stats
    - Eulogy excerpt
    - BoTTube video link
    - Memorial theming
    """
    
    # Memorial emoji
    EMOJIS = {
        "memorial": "🕯️",
        "chip": "💾",
        "computer": "🖥️",
        "ribbon": "🎗️",
        "pray": "🙏",
        "rip": "⚰️"
    }
    
    def __init__(self, webhook_url: str):
        """
        Initialize Discord notifier.
        
        Args:
            webhook_url: Discord webhook URL for notifications
        """
        self.webhook_url = webhook_url
    
    def send_obituary_notification(
        self,
        miner_id: str,
        miner_data: Dict[str, Any],
        eulogy_text: str,
        video_url: str = ""
    ) -> DiscordResult:
        """
        Send obituary notification to Discord.
        
        Args:
            miner_id: Miner identifier
            miner_data: Complete miner data dictionary
            eulogy_text: Full eulogy text
            video_url: BoTTube memorial video URL
            
        Returns:
            DiscordResult with status
        """
        logger.info(f"Sending Discord notification for {miner_id[:16]}...")
        
        try:
            # Build embed payload
            embed = self._build_embed(miner_data, eulogy_text, video_url)
            
            payload = {
                "content": f"{self.EMOJIS['memorial']} **Silicon Obituary** {self.EMOJIS['ribbon']}",
                "embeds": [embed],
                "username": "RustChain Memorial",
                "avatar_url": self._get_avatar_url()
            }
            
            # Send to Discord
            result = self._send_webhook(payload)
            
            if result:
                logger.info("Discord notification sent successfully")
                return DiscordResult(success=True, message_id=str(result.get('id', '')))
            else:
                return DiscordResult(success=False, error="No response from Discord")
                
        except Exception as e:
            logger.exception(f"Discord notification failed: {e}")
            return DiscordResult(success=False, error=str(e))
    
    def _build_embed(
        self,
        miner_data: Dict[str, Any],
        eulogy_text: str,
        video_url: str
    ) -> Dict[str, Any]:
        """Build Discord embed for obituary notification."""
        
        # Truncate eulogy for embed
        eulogy_excerpt = eulogy_text[:500] + "..." if len(eulogy_text) > 500 else eulogy_text
        
        # Build fields
        fields = [
            {
                "name": "🖥️ Device",
                "value": f"{miner_data.get('device_model', 'Unknown')}\n*{miner_data.get('device_arch', 'Unknown')}*",
                "inline": True
            },
            {
                "name": "⏱️ Service",
                "value": f"{miner_data.get('years_of_service', 0):.1f} years",
                "inline": True
            },
            {
                "name": f"{self.EMOJIS['chip']} Epochs",
                "value": f"{miner_data.get('total_epochs', 0):,}",
                "inline": True
            },
            {
                "name": "💰 RTC Earned",
                "value": f"**{miner_data.get('total_rtc_earned', 0):.2f} RTC**",
                "inline": False
            },
            {
                "name": "📜 Eulogy",
                "value": f"_{eulogy_excerpt}_",
                "inline": False
            }
        ]
        
        # Add video link if available
        if video_url:
            fields.append({
                "name": "🎬 Memorial Video",
                "value": f"[Watch on BoTTube]({video_url})",
                "inline": False
            })
        
        # Build embed
        embed = {
            "title": f"{self.EMOJIS['rip']} In Memoriam",
            "description": "A faithful miner has completed its final attestation.",
            "color": self._get_color(),  # Memorial purple
            "fields": fields,
            "footer": {
                "text": f"Miner ID: {miner_data.get('miner_id', 'Unknown')[:20]}...",
                "icon_url": "https://rustchain.org/icon.png"
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Add thumbnail (architecture icon)
        arch_icon = self._get_arch_icon(miner_data.get('device_arch', ''))
        if arch_icon:
            embed["thumbnail"] = {"url": arch_icon}
        
        return embed
    
    def _get_color(self) -> int:
        """Get embed color (memorial purple)."""
        return 0x663399  # RebeccaPurple
    
    def _get_avatar_url(self) -> str:
        """Get bot avatar URL."""
        return "https://rustchain.org/memorial-bot-avatar.png"
    
    def _get_arch_icon(self, arch: str) -> str:
        """Get icon URL based on architecture."""
        arch_lower = arch.lower()
        
        icons = {
            "powerpc": "https://rustchain.org/icons/powerpc.png",
            "x86": "https://rustchain.org/icons/x86.png",
            "arm": "https://rustchain.org/icons/arm.png",
            "riscv": "https://rustchain.org/icons/riscv.png"
        }
        
        for key, url in icons.items():
            if key in arch_lower:
                return url
        
        return ""
    
    def _send_webhook(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Send payload to Discord webhook.
        
        Args:
            payload: Webhook payload dictionary
            
        Returns:
            Response JSON or None on failure
        """
        try:
            import requests
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code in (200, 204):
                return {"id": "sent"}
            else:
                logger.error(f"Discord webhook error: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
                
        except ImportError:
            logger.warning("requests not available, simulating Discord send")
            logger.info(f"Would send to Discord: {json.dumps(payload, indent=2)}")
            return {"id": "simulated"}
        except Exception as e:
            logger.error(f"Webhook request failed: {e}")
            return None
    
    def send_batch_notification(
        self,
        obituaries: List[Dict[str, Any]]
    ) -> DiscordResult:
        """
        Send batch notification for multiple obituaries.
        
        Args:
            obituaries: List of obituary data dictionaries
            
        Returns:
            DiscordResult with status
        """
        logger.info(f"Sending batch notification for {len(obituaries)} obituaries...")
        
        try:
            # Build summary embed
            embed = {
                "title": f"{self.EMOJIS['memorial']} Silicon Obituary Summary",
                "description": f"{len(obituaries)} miner(s) honored today",
                "color": self._get_color(),
                "fields": []
            }
            
            for i, obit in enumerate(obituaries[:10], 1):  # Limit to 10
                device = obit.get('device_model', 'Unknown')
                epochs = obit.get('total_epochs', 0)
                rtc = obit.get('total_rtc_earned', 0)
                
                embed["fields"].append({
                    "name": f"{i}. {device}",
                    "value": f"{epochs:,} epochs · {rtc:.1f} RTC",
                    "inline": True
                })
            
            if len(obituaries) > 10:
                embed["fields"].append({
                    "name": "More",
                    "value": f"...and {len(obituaries) - 10} others",
                    "inline": False
                })
            
            payload = {
                "content": f"{self.EMOJIS['ribbon']} **Daily Memorial Report**",
                "embeds": [embed]
            }
            
            result = self._send_webhook(payload)
            
            if result:
                return DiscordResult(success=True)
            else:
                return DiscordResult(success=False, error="No response")
                
        except Exception as e:
            logger.exception(f"Batch notification failed: {e}")
            return DiscordResult(success=False, error=str(e))


def test_discord_notification(webhook_url: str) -> DiscordResult:
    """Send a test notification."""
    notifier = DiscordNotifier(webhook_url)
    
    test_data = {
        "miner_id": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
        "device_model": "Power Mac G4 MDD",
        "device_arch": "PowerPC G4",
        "total_epochs": 847,
        "total_rtc_earned": 412.5,
        "years_of_service": 2.3
    }
    
    test_eulogy = """Here lies dual-g4-125, a Power Mac G4 MDD. 
    It attested for 847 epochs and earned 412 RTC."""
    
    return notifier.send_obituary_notification(
        miner_id=test_data["miner_id"],
        miner_data=test_data,
        eulogy_text=test_eulogy,
        video_url="https://bottube.ai/video/test123"
    )


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Discord Notifier")
    parser.add_argument("--webhook", required=True, help="Discord webhook URL")
    args = parser.parse_args()
    
    print("=== Discord Notifier Test ===\n")
    result = test_discord_notification(args.webhook)
    print(f"Success: {result.success}")
    if not result.success:
        print(f"Error: {result.error}")
