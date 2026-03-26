"""
Vintage AI Miner Video Pipeline
================================

Automated pipeline for generating AI videos of vintage hardware mining RustChain.

Issue: #1855
Bounty: 150 RTC + bonuses

Components:
- rustchain_client: RustChain API integration
- prompt_generator: Video prompt generation
- video_generator: AI video generation
- bottube_uploader: BoTTube platform upload
- pipeline: Main orchestrator

Usage:
    from vintage_ai_video_pipeline import VintageAIVideoPipeline
    
    pipeline = VintageAIVideoPipeline()
    pipeline.run_once()
"""

__version__ = "1.0.0"
__author__ = "RustChain Bounty Contributor"

from .rustchain_client import RustChainClient, create_client
from .prompt_generator import VideoPromptGenerator
from .video_generator import VideoGenerator, create_generator
from .bottube_uploader import BoTTubeUploader, create_uploader
from .pipeline import VintageAIVideoPipeline

__all__ = [
    "RustChainClient",
    "create_client",
    "VideoPromptGenerator",
    "VideoGenerator",
    "create_generator",
    "BoTTubeUploader",
    "create_uploader",
    "VintageAIVideoPipeline",
]
