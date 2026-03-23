"""
Hardware Eulogy Generator - Bounty #2308
========================================

Generates poetic "eulogies" for miners that have permanently gone offline.

When a miner hasn't attested for 7+ days, this module:
1. Detects the offline miner
2. Extracts mining statistics from the database
3. Generates a poetic eulogy text (LLM-assisted)
4. Creates a BoTTube video with:
   - Machine photo or architecture icon
   - Eulogy as narration (TTS)
   - Background music
   - RTC earnings counter animation
5. Sends Discord notification

Author: HuiNeng
Bounty: #2308 - Hardware Eulogy Generator (25 RTC)
Wallet: 9dRRMiHiJwjF3VW8pXtKDtpmmxAPFy3zWgV2JY5H6eeT
"""

from .detector import OfflineMinerDetector
from .eulogy_generator import EulogyGenerator
from .video_creator import VideoCreator
from .discord_notifier import DiscordNotifier
from .models import MinerProfile, EulogyData

__version__ = "1.0.0"
__all__ = [
    "OfflineMinerDetector",
    "EulogyGenerator", 
    "VideoCreator",
    "DiscordNotifier",
    "MinerProfile",
    "EulogyData",
]