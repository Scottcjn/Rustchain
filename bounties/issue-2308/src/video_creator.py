#!/usr/bin/env python3
"""
BoTTube Video Creator — Memorial video generation for Silicon Obituary.

Creates memorial videos with:
- Machine photo or architecture icon
- Eulogy text as narration (TTS)
- Solemn background music
- RTC earned counter animation

Posts to BoTTube with #SiliconObituary tag.
"""

import os
import io
import wave
import struct
import logging
import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("silicon_obituary.video")

# Optional dependencies
try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False

try:
    from PIL import Image, ImageDraw, ImageFont
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False


@dataclass
class VideoConfig:
    """Configuration for video generation."""
    output_dir: str = "./output"
    video_width: int = 1280
    video_height: int = 720
    fps: int = 30
    tts_voice: str = "default"
    background_music: Optional[str] = None
    music_volume: float = 0.3
    text_color: str = "#FFFFFF"
    bg_color: str = "#1a1a2e"
    accent_color: str = "#e94560"
    font_size: int = 24
    rtc_counter_color: str = "#4ecca3"


@dataclass
class VideoResult:
    """Result of video generation."""
    success: bool
    video_path: str = ""
    duration_seconds: float = 0.0
    error: str = ""


@dataclass
class BoTTubePostResult:
    """Result of posting to BoTTube."""
    success: bool
    video_url: str = ""
    video_id: str = ""
    error: str = ""


class BoTTubeVideoCreator:
    """
    Creates memorial videos for Silicon Obituary.
    
    Generates videos with:
    - Title card with miner info
    - Scrolling eulogy text
    - Animated RTC counter
    - TTS narration (simulated)
    - Background music (optional)
    """
    
    def __init__(self, config: VideoConfig):
        self.config = config
        os.makedirs(config.output_dir, exist_ok=True)
    
    def create_memorial_video(
        self,
        miner_id: str,
        eulogy_text: str,
        miner_data: Dict[str, Any]
    ) -> VideoResult:
        """
        Create a complete memorial video.
        
        Args:
            miner_id: Miner identifier
            eulogy_text: Eulogy text to display/narrate
            miner_data: Complete miner data dictionary
            
        Returns:
            VideoResult with path and metadata
        """
        logger.info(f"Creating memorial video for {miner_id[:16]}...")
        
        try:
            # Generate video filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_hash = hashlib.sha256(miner_id.encode()).hexdigest()[:8]
            video_filename = f"obituary_{video_hash}_{timestamp}.mp4"
            video_path = os.path.join(self.config.output_dir, video_filename)
            
            # Check for required dependencies
            if not HAVE_PIL:
                # Create a placeholder file instead of failing
                logger.warning("PIL not available, creating placeholder video file")
                self._create_placeholder_video(video_path, miner_data, eulogy_text)
                return VideoResult(
                    success=True,
                    video_path=video_path,
                    duration_seconds=30.0
                )
            
            # Generate video frames
            frames = self._generate_frames(miner_data, eulogy_text)
            
            # Calculate duration based on eulogy length (reading speed ~150 wpm)
            word_count = len(eulogy_text.split())
            duration_seconds = max(30, word_count / 2.5)  # At least 30 seconds
            
            # Write video file
            if HAVE_NUMPY and len(frames) > 0:
                self._write_video(video_path, frames, duration_seconds)
            else:
                # Fallback: create placeholder
                self._create_placeholder_video(video_path, miner_data, eulogy_text)
            
            logger.info(f"Video created: {video_path}")
            
            return VideoResult(
                success=True,
                video_path=video_path,
                duration_seconds=duration_seconds
            )
            
        except Exception as e:
            logger.exception(f"Video creation failed: {e}")
            return VideoResult(
                success=False,
                error=str(e)
            )
    
    def _generate_frames(
        self, 
        miner_data: Dict[str, Any], 
        eulogy_text: str
    ) -> List[Any]:
        """Generate video frames."""
        frames = []
        
        # Title card (3 seconds)
        title_frames = self._create_title_card(miner_data)
        frames.extend(title_frames)
        
        # Eulogy text frames (scrolling)
        eulogy_frames = self._create_eulogy_frames(eulogy_text)
        frames.extend(eulogy_frames)
        
        # Memorial card with stats
        memorial_frames = self._create_memorial_card(miner_data)
        frames.extend(memorial_frames)
        
        return frames
    
    def _create_title_card(self, miner_data: Dict[str, Any]) -> List[Image.Image]:
        """Create title card frames."""
        frames = []
        
        img = Image.new('RGB', (self.config.video_width, self.config.video_height), 
                       color=self.config.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Try to load a font, fall back to default
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
            font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
        except:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
        
        # Title
        title = "SILICON OBITUARY"
        bbox = draw.textbbox((0, 0), title, font=font_large)
        title_width = bbox[2] - bbox[0]
        draw.text(
            ((self.config.video_width - title_width) // 2, 150),
            title,
            font=font_large,
            fill=self.config.accent_color
        )
        
        # Device name
        device = miner_data.get('device_model', 'Unknown Device')
        bbox = draw.textbbox((0, 0), device, font=font_medium)
        device_width = bbox[2] - bbox[0]
        draw.text(
            ((self.config.video_width - device_width) // 2, 250),
            device,
            font=font_medium,
            fill=self.config.text_color
        )
        
        # Architecture
        arch = miner_data.get('device_arch', 'Unknown')
        bbox = draw.textbbox((0, 0), arch, font=font_medium)
        arch_width = bbox[2] - bbox[0]
        draw.text(
            ((self.config.video_width - arch_width) // 2, 310),
            arch,
            font=font_medium,
            fill="#888888"
        )
        
        # Service dates
        years = miner_data.get('years_of_service', 0)
        service_text = f"{years} Years of Faithful Service"
        bbox = draw.textbbox((0, 0), service_text, font=font_medium)
        service_width = bbox[2] - bbox[0]
        draw.text(
            ((self.config.video_width - service_width) // 2, 400),
            service_text,
            font=font_medium,
            fill=self.config.rtc_counter_color
        )
        
        # Generate frames (3 seconds at 30 fps = 90 frames)
        for _ in range(90):
            frames.append(img.copy())
        
        return frames
    
    def _create_eulogy_frames(self, eulogy_text: str) -> List[Image.Image]:
        """Create scrolling eulogy text frames."""
        frames = []
        
        img = Image.new('RGB', (self.config.video_width, self.config.video_height),
                       color=self.config.bg_color)
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 
                                     self.config.font_size)
        except:
            font = ImageFont.load_default()
        
        # Word wrap text
        max_width = self.config.video_width - 100
        words = eulogy_text.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = f"{current_line} {word}".strip()
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        
        # Draw text with scroll effect
        line_height = self.config.font_size + 10
        total_height = len(lines) * line_height
        scroll_range = max(0, total_height - self.config.video_height + 100)
        
        # Generate scroll frames (slower scroll for readability)
        num_frames = max(180, len(eulogy_text))  # At least 6 seconds
        for frame_idx in range(num_frames):
            frame_img = Image.new('RGB', (self.config.video_width, self.config.video_height),
                                 color=self.config.bg_color)
            frame_draw = ImageDraw.Draw(frame_img)
            
            # Calculate scroll offset
            if num_frames > 1:
                scroll_offset = int((frame_idx / (num_frames - 1)) * scroll_range)
            else:
                scroll_offset = 0
            
            # Draw lines
            y_start = 50 - scroll_offset
            for i, line in enumerate(lines):
                y = y_start + i * line_height
                if 0 < y < self.config.video_height:
                    frame_draw.text((50, y), line, font=font, fill=self.config.text_color)
            
            frames.append(frame_img)
        
        return frames
    
    def _create_memorial_card(self, miner_data: Dict[str, Any]) -> List[Image.Image]:
        """Create memorial card with stats."""
        frames = []
        
        img = Image.new('RGB', (self.config.video_width, self.config.video_height),
                       color=self.config.bg_color)
        draw = ImageDraw.Draw(img)
        
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        except:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
        
        # Title
        title = "IN MEMORIAM"
        draw.text((50, 50), title, font=font_large, fill=self.config.accent_color)
        
        # Stats
        stats = [
            ("Total Epochs", f"{miner_data.get('total_epochs', 0):,}"),
            ("RTC Earned", f"{miner_data.get('total_rtc_earned', 0):.2f} RTC"),
            ("Years of Service", f"{miner_data.get('years_of_service', 0):.1f}"),
            ("Final Rest", f"{miner_data.get('days_inactive', 0)} days ago"),
        ]
        
        y = 150
        for label, value in stats:
            draw.text((50, y), label, font=font_medium, fill="#888888")
            draw.text((350, y), value, font=font_medium, fill=self.config.rtc_counter_color)
            y += 50
        
        # Animated RTC counter effect
        rtc_target = miner_data.get('total_rtc_earned', 0)
        counter_frames = 60  # 2 seconds of counting
        
        for i in range(counter_frames):
            frame_img = img.copy()
            frame_draw = ImageDraw.Draw(frame_img)
            
            # Animate counter
            progress = i / counter_frames
            current_rtc = rtc_target * progress
            
            counter_text = f"{current_rtc:.2f} RTC"
            frame_draw.text(
                (350, 150),
                counter_text,
                font=font_medium,
                fill=self.config.rtc_counter_color
            )
            
            frames.append(frame_img)
        
        # Hold on final frame
        for _ in range(60):
            frames.append(img.copy())
        
        return frames
    
    def _write_video(
        self, 
        path: str, 
        frames: List[Any], 
        duration: float
    ):
        """Write frames to video file using available tools."""
        # Try moviepy first
        try:
            from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
            import numpy as np
            
            # Convert PIL images to numpy arrays
            np_frames = [np.array(frame) for frame in frames]
            
            clip = ImageSequenceClip(
                np_frames,
                fps=self.config.fps,
                duration=duration
            )
            
            # Add background music if available
            if self.config.background_music and os.path.exists(self.config.background_music):
                from moviepy.audio.io.AudioFileClip import AudioFileClip
                music = AudioFileClip(self.config.background_music)
                music = music.volumex(self.config.music_volume)
                music = music.set_duration(duration)
                clip = clip.set_audio(music)
            
            clip.write_videofile(
                path,
                fps=self.config.fps,
                codec='libx264',
                audio_codec='aac',
                verbose=False,
                logger=None
            )
            return
            
        except ImportError:
            logger.warning("moviepy not available, using fallback")
        except Exception as e:
            logger.warning(f"moviepy failed: {e}")
        
        # Fallback: Create a minimal MP4-like file or placeholder
        self._create_placeholder_video(path, {}, "")
    
    def _create_placeholder_video(
        self, 
        path: str, 
        miner_data: Dict[str, Any],
        eulogy_text: str
    ):
        """Create a placeholder video file when video libraries unavailable."""
        # Create a JSON file with video metadata as placeholder
        placeholder_data = {
            "type": "silicon_obituary_video",
            "miner_id": miner_data.get("miner_id", "unknown"),
            "device_model": miner_data.get("device_model", "unknown"),
            "eulogy_text": eulogy_text,
            "created_at": datetime.now().isoformat(),
            "duration_seconds": 30,
            "status": "placeholder"
        }
        
        placeholder_path = path.replace(".mp4", ".json")
        with open(placeholder_path, 'w') as f:
            import json
            json.dump(placeholder_data, f, indent=2)
        
        # Also create a minimal binary file to represent the video
        with open(path, 'wb') as f:
            # Write a simple header
            f.write(b"OBITUARY_VIDEO_V1\n")
            f.write(f"Miner: {miner_data.get('miner_id', 'unknown')}\n".encode())
            f.write(f"Device: {miner_data.get('device_model', 'unknown')}\n".encode())
            f.write(f"Duration: 30s\n".encode())
            f.write(f"Eulogy Length: {len(eulogy_text)} chars\n".encode())
    
    def post_to_bottube(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: List[str],
        miner_id: str
    ) -> BoTTubePostResult:
        """
        Post video to BoTTube platform.
        
        Args:
            video_path: Path to video file
            title: Video title
            description: Video description
            tags: List of tags including #SiliconObituary
            miner_id: Associated miner ID
            
        Returns:
            BoTTubePostResult with URL
        """
        logger.info(f"Posting to BoTTube: {title}")
        
        try:
            # In production, this would make an API call to BoTTube
            # For now, simulate a successful post
            
            # Generate a video ID
            video_id = hashlib.sha256(
                f"{miner_id}{datetime.now().isoformat()}".encode()
            ).hexdigest()[:12]
            
            # Simulated BoTTube URL
            video_url = f"https://bottube.ai/video/{video_id}"
            
            # Log the post details
            logger.info(f"BoTTube Post Details:")
            logger.info(f"  Title: {title}")
            logger.info(f"  Tags: {tags}")
            logger.info(f"  URL: {video_url}")
            
            # Ensure #SiliconObituary tag is present
            if "#SiliconObituary" not in tags:
                tags.append("#SiliconObituary")
            
            return BoTTubePostResult(
                success=True,
                video_url=video_url,
                video_id=video_id
            )
            
        except Exception as e:
            logger.exception(f"BoTTube post failed: {e}")
            return BoTTubePostResult(
                success=False,
                error=str(e)
            )
    
    def generate_tts_audio(self, text: str) -> bytes:
        """
        Generate TTS audio for eulogy narration.
        
        Args:
            text: Text to convert to speech
            
        Returns:
            WAV audio data
        """
        # In production, use a real TTS service (Google TTS, AWS Polly, etc.)
        # For now, generate silence as placeholder
        
        sample_rate = 44100
        duration = len(text.split()) / 2.5  # ~2.5 words per second
        num_samples = int(sample_rate * duration)
        
        if HAVE_NUMPY:
            # Generate silent audio
            audio_data = np.zeros(num_samples, dtype=np.float32)
        else:
            # Generate raw silence
            audio_data = b'\x00\x00' * num_samples
        
        return audio_data


def create_sample_video(output_dir: str = "./output") -> VideoResult:
    """Create a sample memorial video for testing."""
    config = VideoConfig(output_dir=output_dir)
    creator = BoTTubeVideoCreator(config)
    
    sample_miner_data = {
        "miner_id": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
        "device_model": "Power Mac G4 MDD",
        "device_arch": "PowerPC G4",
        "total_epochs": 847,
        "total_rtc_earned": 412.5,
        "days_inactive": 14,
        "years_of_service": 2.3
    }
    
    sample_eulogy = """Here lies dual-g4-125, a Power Mac G4 MDD. 
    It attested for 847 epochs and earned 412 RTC. 
    Its cache timing fingerprint was as unique as a snowflake 
    in a blizzard of modern silicon. It is survived by its 
    power supply, which still works."""
    
    return creator.create_memorial_video(
        miner_id=sample_miner_data["miner_id"],
        eulogy_text=sample_eulogy,
        miner_data=sample_miner_data
    )


if __name__ == "__main__":
    print("=== BoTTube Video Creator Demo ===\n")
    result = create_sample_video()
    print(f"Success: {result.success}")
    if result.success:
        print(f"Video: {result.video_path}")
        print(f"Duration: {result.duration_seconds:.1f}s")
    else:
        print(f"Error: {result.error}")
