#!/usr/bin/env python3
"""
Video Prompt Generator for Vintage AI Miner Videos
===================================================

Generates detailed video generation prompts based on miner metadata.
Supports multiple visual styles and video generation backends.
"""

import random
from typing import Dict, Any, List, Optional
from datetime import datetime


class VideoPromptGenerator:
    """
    Generates video prompts for AI video generation backends
    
    Supports:
    - LTX-Video
    - CogVideo
    - Mochi
    - Other open video models
    """

    # Visual style templates for different hardware eras
    VISUAL_STYLES = {
        "vintage_apple_beige_aesthetic": {
            "description": "1990s Apple Macintosh beige aesthetic with curved plastic",
            "color_palette": ["beige", "cream", "soft gray", "amber glow"],
            "lighting": "warm CRT monitor glow",
            "atmosphere": "nostalgic, cozy, retro-futuristic",
        },
        "retro_apple_performera_style": {
            "description": "Early 1990s Macintosh Performera all-in-one design",
            "color_palette": ["pearl white", "dark gray accents", "phosphor green"],
            "lighting": "soft ambient with monitor flicker",
            "atmosphere": "vintage computing, educational, approachable",
        },
        "powermac_g5_aluminum_cool": {
            "description": "2000s PowerMac G5 brushed aluminum aesthetic",
            "color_palette": ["silver", "aluminum", "cool blue LEDs"],
            "lighting": "clean, modern, LED indicators",
            "atmosphere": "sleek, professional, high-performance",
        },
        "ibm_power7_server_industrial": {
            "description": "IBM Power7 server industrial design",
            "color_palette": ["black", "steel gray", "blue status lights"],
            "lighting": "datacenter fluorescent with LED accents",
            "atmosphere": "enterprise, powerful, reliable",
        },
        "ibm_power8_datacenter": {
            "description": "IBM Power8 enterprise server environment",
            "color_palette": ["matte black", "rack silver", "multicolor LEDs"],
            "lighting": "server room ambient with blinking lights",
            "atmosphere": "industrial, computing power, 24/7 operation",
        },
        "modern_server_rack": {
            "description": "Modern x86 server rack environment",
            "color_palette": ["black", "silver", "RGB accents"],
            "lighting": "LED status indicators, cool white",
            "atmosphere": "modern datacenter, cloud computing",
        },
        "modern_arm_cluster": {
            "description": "Modern ARM-based computing cluster",
            "color_palette": ["green PCB", "black heatsinks", "blue LEDs"],
            "lighting": "clean, efficient, minimalist",
            "atmosphere": "energy-efficient, modern, scalable",
        },
        "vintage_computer_generic": {
            "description": "Generic vintage computer aesthetic",
            "color_palette": ["beige", "gray", "amber", "green phosphor"],
            "lighting": "CRT monitor glow, dim room lighting",
            "atmosphere": "retro computing, nostalgic, warm",
        },
    }

    # Mining visualization elements
    MINING_ELEMENTS = [
        "cryptographic hash functions visualized as flowing data streams",
        "blockchain blocks forming and connecting in sequence",
        "digital tokens being minted with metallic shine",
        "network nodes connecting with glowing lines",
        "proof-of-work puzzles solving with satisfying clicks",
        "distributed ledger updating in real-time",
        "consensus algorithm visualization",
        "peer-to-peer network topology",
    ]

    # Era-specific animations
    ERA_ANIMATIONS = {
        "vintage": [
            "CRT monitor scanlines",
            "pixel art transitions",
            "dithering effects",
            "low-poly 3D models",
            "terminal text scrolling",
        ],
        "modern": [
            "smooth particle effects",
            "volumetric lighting",
            "procedural animations",
            "real-time ray tracing hints",
            "holographic displays",
        ],
        "industrial": [
            "mechanical moving parts",
            "cooling fans spinning",
            "cable management aesthetics",
            "rack mount animations",
            "status LED patterns",
        ],
    }

    def __init__(self, backend: str = "ltx-video"):
        """
        Initialize prompt generator
        
        Args:
            backend: Target video generation backend (ltx-video, cogvideo, mochi)
        """
        self.backend = backend
        self.prompt_templates = self._get_backend_templates()

    def _get_backend_templates(self) -> Dict[str, str]:
        """Get prompt templates optimized for each backend"""
        return {
            "ltx-video": self._ltx_template(),
            "cogvideo": self._cogvideo_template(),
            "mochi": self._mochi_template(),
            "default": self._default_template(),
        }

    def _ltx_template(self) -> str:
        """LTX-Video optimized template"""
        return """
{scene_description}, {visual_style} aesthetic. {hardware_description} mining RustChain cryptocurrency. 
{mining_visualization} with {era_effects}. 
Color palette: {colors}. Lighting: {lighting}. Atmosphere: {atmosphere}.
Technical: high quality, detailed, smooth motion, 24fps, vintage hardware showcase.
Wallet: {wallet_id}, Epoch: {epoch}, Reward: {reward} RTC, Multiplier: x{multiplier}
""".strip()

    def _cogvideo_template(self) -> str:
        """CogVideo optimized template"""
        return """
A cinematic shot of {hardware_description} from the {era} era mining RustChain blockchain.
Visual style: {visual_style}. {mining_visualization}.
{era_effects} effects. Colors include {colors}.
The scene has {lighting} lighting creating a {atmosphere} mood.
On-screen text shows wallet {wallet_id}, epoch {epoch}, reward {reward} RTC.
High quality AI video, smooth animation, detailed vintage computer.
Antiquity multiplier: x{multiplier}.
""".strip()

    def _mochi_template(self) -> str:
        """Mochi optimized template"""
        return """
{hardware_description} performing RustChain mining operations.
Style reference: {visual_style}. 
{mining_visualization} visualized as {mining_metaphor}.
{era_effects}. Palette: {colors}. {lighting}. {atmosphere}.
Display shows: Wallet {wallet_id} | Epoch {epoch} | {reward} RTC | x{multiplier}
Professional video quality, smooth motion, vintage computing aesthetic.
""".strip()

    def _default_template(self) -> str:
        """Default template for unknown backends"""
        return """
{hardware_description} mining RustChain. {visual_style} style.
{mining_visualization}. {era_effects}.
Colors: {colors}. Lighting: {lighting}. Mood: {atmosphere}.
Stats: {wallet_id}, Epoch {epoch}, {reward} RTC, x{multiplier}
High quality, detailed, smooth animation.
""".strip()

    def generate_prompt(
        self,
        miner_data: Dict[str, Any],
        epoch_info: Optional[Dict[str, Any]] = None,
        custom_style: Optional[str] = None,
        include_text_overlay: bool = True,
        duration_hint: str = "5s"
    ) -> Dict[str, Any]:
        """
        Generate a complete video prompt from miner data
        
        Args:
            miner_data: Formatted miner data from RustChainClient
            epoch_info: Current epoch information
            custom_style: Override visual style
            include_text_overlay: Include wallet/epoch info as text
            duration_hint: Suggested video duration
            
        Returns:
            Dictionary with prompt and metadata
        """
        # Extract miner info
        hardware = miner_data.get("hardware_type", "Vintage Computer")
        device_arch = miner_data.get("device_arch", "Unknown")
        device_family = miner_data.get("device_family", "Unknown")
        multiplier = miner_data.get("antiquity_multiplier", 1.0)
        wallet_id = miner_data.get("short_id", "????")
        visual_style_key = miner_data.get("visual_style", "vintage_computer_generic")
        
        # Get visual style config
        style_config = self.VISUAL_STYLES.get(
            custom_style or visual_style_key,
            self.VISUAL_STYLES["vintage_computer_generic"]
        )
        
        # Determine era
        era = self._classify_era(device_arch, device_family)
        
        # Generate scene description
        scene_desc = self._generate_scene_description(
            hardware, device_arch, era
        )
        
        # Select mining visualization
        mining_viz = random.choice(self.MINING_ELEMENTS)
        mining_metaphor = self._get_mining_metaphor(era)
        
        # Get era-specific effects
        era_effects = ", ".join(
            random.sample(self.ERA_ANIMATIONS.get(era, self.ERA_ANIMATIONS["vintage"]), 2)
        )
        
        # Get template for backend
        template = self.prompt_templates.get(
            self.backend,
            self.prompt_templates["default"]
        )
        
        # Format colors
        colors = ", ".join(style_config["color_palette"][:3])
        
        # Generate prompt
        prompt = template.format(
            scene_description=scene_desc,
            visual_style=style_config["description"],
            hardware_description=hardware,
            mining_visualization=mining_viz.capitalize(),
            mining_metaphor=mining_metaphor,
            era_effects=era_effects.capitalize(),
            colors=colors,
            lighting=style_config["lighting"],
            atmosphere=style_config["atmosphere"],
            era=era,
            wallet_id=wallet_id,
            epoch=epoch_info.get("epoch", "?") if epoch_info else "?",
            reward=self._generate_reward_display(multiplier),
            multiplier=multiplier,
        )
        
        # Build negative prompt (for backends that support it)
        negative_prompt = self._generate_negative_prompt(era)
        
        return {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "backend": self.backend,
            "style": custom_style or visual_style_key,
            "era": era,
            "duration_hint": duration_hint,
            "include_text_overlay": include_text_overlay,
            "metadata": {
                "miner_id": miner_data.get("miner_id", ""),
                "device_arch": device_arch,
                "device_family": device_family,
                "antiquity_multiplier": multiplier,
                "epoch": epoch_info.get("epoch") if epoch_info else None,
                "generated_at": datetime.utcnow().isoformat(),
            },
            "suggested_tags": self._generate_tags(
                device_arch, device_family, era, multiplier
            ),
        }

    def _classify_era(self, device_arch: str, device_family: str) -> str:
        """Classify hardware into era category"""
        vintage_archs = ["G3", "G4", "G5", "POWER3", "POWER4", "POWER5", "POWER6", "POWER7"]
        industrial_archs = ["POWER7", "POWER8", "POWER9"]
        
        if device_arch in vintage_archs or "PowerPC" in device_family:
            return "vintage"
        elif device_arch in industrial_archs or "POWER" in device_family:
            return "industrial"
        else:
            return "modern"

    def _generate_scene_description(
        self,
        hardware: str,
        device_arch: str,
        era: str
    ) -> str:
        """Generate detailed scene description"""
        templates = {
            "vintage": [
                f"A beautifully preserved {hardware} from the classic computing era",
                f"Nostalgic {hardware} with period-correct aesthetics",
                f"Vintage {hardware} showcasing retro computing excellence",
            ],
            "modern": [
                f"Modern {hardware} with contemporary design",
                f"Sleek {hardware} representing current computing technology",
                f"Contemporary {hardware} with cutting-edge aesthetics",
            ],
            "industrial": [
                f"Industrial-grade {hardware} built for enterprise workloads",
                f"Enterprise {hardware} in a professional datacenter setting",
                f"Server-class {hardware} designed for 24/7 operation",
            ],
        }
        
        return random.choice(templates.get(era, templates["vintage"]))

    def _get_mining_metaphor(self, era: str) -> str:
        """Get era-appropriate mining metaphor"""
        metaphors = {
            "vintage": "digital gold being extracted pixel by pixel",
            "modern": "cryptographic proofs materializing as crystalline structures",
            "industrial": "computational work visualized as flowing energy",
        }
        return metaphors.get(era, metaphors["vintage"])

    def _generate_reward_display(self, multiplier: float) -> str:
        """Generate reward display text"""
        # Simulate reward based on multiplier
        base_reward = 0.5
        simulated_reward = base_reward * multiplier
        return f"{simulated_reward:.2f}"

    def _generate_negative_prompt(self, era: str) -> str:
        """Generate negative prompt for better quality"""
        base_negative = [
            "low quality", "blurry", "distorted", "ugly", "deformed",
            "noisy", "grainy", "oversaturated", "text artifacts",
        ]
        
        era_specific = {
            "vintage": ["modern RGB gaming aesthetics", "excessive neon"],
            "modern": ["outdated CRT effects", "excessive scanlines"],
            "industrial": ["consumer-grade aesthetics", "gaming RGB"],
        }
        
        all_negative = base_negative + era_specific.get(era, [])
        return ", ".join(all_negative)

    def _generate_tags(
        self,
        device_arch: str,
        device_family: str,
        era: str,
        multiplier: float
    ) -> List[str]:
        """Generate suggested video tags"""
        tags = [
            "RustChain",
            "cryptocurrency",
            "mining",
            "blockchain",
            "AI video",
            device_arch,
        ]
        
        if era == "vintage":
            tags.extend(["retro computing", "vintage hardware", "classic computer"])
        elif era == "industrial":
            tags.extend(["datacenter", "enterprise", "server"])
        else:
            tags.extend(["modern computing", "contemporary"])
        
        if multiplier > 2.0:
            tags.append("high multiplier")
        
        tags.append(f"{device_family}")
        
        return tags

    def generate_batch(
        self,
        miners: List[Dict[str, Any]],
        epoch_info: Optional[Dict[str, Any]] = None,
        style_variety: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Generate prompts for multiple miners
        
        Args:
            miners: List of formatted miner data
            epoch_info: Current epoch information
            style_variety: Add variety to visual styles
            
        Returns:
            List of prompt dictionaries
        """
        prompts = []
        
        for miner in miners:
            # Optionally vary the style
            custom_style = None
            if style_variety and random.random() > 0.7:
                custom_style = random.choice(list(self.VISUAL_STYLES.keys()))
            
            prompt_data = self.generate_prompt(
                miner_data=miner,
                epoch_info=epoch_info,
                custom_style=custom_style,
            )
            prompts.append(prompt_data)
        
        return prompts


if __name__ == "__main__":
    # Demo usage
    print("🎬 Video Prompt Generator Demo")
    print("=" * 50)
    
    generator = VideoPromptGenerator(backend="ltx-video")
    
    # Sample miner data
    sample_miner = {
        "miner_id": "eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC",
        "short_id": "eafc6f14",
        "device_arch": "G4",
        "device_family": "PowerPC",
        "hardware_type": "PowerPC G4 (Vintage)",
        "antiquity_multiplier": 2.5,
        "entropy_score": 0.0,
        "visual_style": "vintage_apple_beige_aesthetic",
    }
    
    epoch_info = {"epoch": 75, "slot": 10800}
    
    prompt_data = generator.generate_prompt(
        miner_data=sample_miner,
        epoch_info=epoch_info,
    )
    
    print("\n📝 Generated Prompt:")
    print("-" * 50)
    print(prompt_data["prompt"])
    print("\n🚫 Negative Prompt:")
    print(prompt_data["negative_prompt"])
    print("\n🏷️  Suggested Tags:")
    print(", ".join(prompt_data["suggested_tags"]))
    print("\n📊 Metadata:")
    for key, value in prompt_data["metadata"].items():
        print(f"  {key}: {value}")
