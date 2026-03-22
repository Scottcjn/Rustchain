#!/usr/bin/env python3
"""
Eulogy Generator — Poetic hardware obituaries for retired miners.

Generates meaningful eulogy text incorporating actual miner statistics
like attestation count, RTC earned, architecture, and years of service.

Supports multiple eulogy styles:
- Poetic: Lyrical and emotional
- Technical: Focus on specs and achievements
- Humorous: Light-hearted send-off
- Epic: Grand heroic narrative
"""

import random
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("silicon_obituary.eulogy")


@dataclass
class EulogyData:
    """Data required for eulogy generation."""
    miner_id: str
    device_model: str
    device_arch: str
    total_epochs: int
    total_rtc_earned: float
    days_inactive: int
    years_of_service: float
    first_attestation: str
    last_attestation: str
    multiplier_history: List[float]
    
    @classmethod
    def from_miner_data(cls, data: Dict[str, Any]) -> "EulogyData":
        """Create EulogyData from miner data dictionary."""
        return cls(
            miner_id=data.get("miner_id", "Unknown"),
            device_model=data.get("device_model", "Unknown Device"),
            device_arch=data.get("device_arch", "Unknown"),
            total_epochs=data.get("total_epochs", 0),
            total_rtc_earned=data.get("total_rtc_earned", 0.0),
            days_inactive=data.get("days_inactive", 0),
            years_of_service=data.get("years_of_service", 0.0),
            first_attestation=data.get("first_attestation", ""),
            last_attestation=data.get("last_attestation", ""),
            multiplier_history=data.get("multiplier_history", [])
        )


class EulogyGenerator:
    """
    Generates poetic eulogies for retired mining hardware.
    
    Combines real miner statistics with templated prose to create
    meaningful send-offs for hardware that has served the network.
    """
    
    # Eulogy templates by style
    TEMPLATES = {
        "poetic": [
            """Here lies {device}, a {arch}. It attested for {epochs} epochs and earned {rtc} RTC. 
Its {unique_feature} was as unique as a snowflake in a blizzard of modern silicon. 
It served faithfully for {years} years, from {start} to {end}. 
It is survived by its {survivor}, which still works.""",
            
            """In memory of {device}, warrior of the vintage silicon age. 
For {years} years it stood guard over the RustChain, validating {epochs} epochs 
and amassing {rtc} RTC in tribute. Though its {component} now rests, 
its spirit lives on in every block it helped secure.""",
            
            """{device} ({arch}) — {start} to {end}. 
A faithful servant of {years} years, it processed {epochs} attestations 
and earned {rtc} RTC. Like all great pioneers, it has now returned to the 
silicon from whence it came. Rest in power, old friend."""
        ],
        
        "technical": [
            """MINER OBITUARY: {device}
Architecture: {arch}
Service Period: {years} years ({start} to {end})
Total Attestations: {epochs} epochs
RTC Mined: {rtc}
Average Multiplier: {avg_mult}x
Status: Retired (inactive {days} days)
Cause: Hardware retirement
Survived by: {survivor}""",
            
            """END OF LIFE NOTICE
Device: {device} ({arch})
Uptime: {years} years
Blocks Validated: {epochs}
Rewards Earned: {rtc} RTC
Final Attestation: {end}
Reason: {days} days inactive
Legacy: {legacy}"""
        ],
        
        "humorous": [
            """{device} has officially kicked the bucket. 
After {years} years of proving it wasn't just a paperweight, 
it attested {epochs} times and earned {rtc} RTC (not bad for a relic!). 
The power supply is still going strong — because of course it is. 
 RIP, you beautiful old dinosaur.""",
            
            """Gone but not forgotten: {device}. 
This {arch} veteran served {years} years, earned {rtc} RTC, 
and never once complained about having to mine with {epochs} epochs worth of data. 
Cause of death: Finally admitting modern hardware exists. 
Survived by its ethernet cable and several loose screws."""
        ],
        
        "epic": [
            """BEHOLD THE FALL OF {device}! 
A {arch} titan who stood against the tide of obsolescence for {years} years! 
It conquered {epochs} epochs, amassed a fortune of {rtc} RTC, 
and never yielded to the whispers of 'upgrade'. 
Though its circuits now sleep, its legend echoes through the blockchain forever!""",
            
            """A HERO HAS FALLEN. {device}, champion of the {arch} age, 
has completed its final attestation. For {years} years it defended 
the RustChain against {epochs} epochs of uncertainty, earning {rtc} RTC 
in glory. Let all miners bow their heads as we welcome it into 
the great mining pool in the sky."""
        ]
    }
    
    # Unique features by architecture
    UNIQUE_FEATURES = {
        "powerpc": "cache timing fingerprint",
        "x86_64": "branch prediction pattern",
        "arm64": "NEON vector dance",
        "ppc64": "AltiVec symphony",
        "default": "silicon fingerprint"
    }
    
    # Components that might "survive"
    SURVIVORS = [
        "power supply",
        "cooling fan",
        "ethernet cable",
        "USB ports",
        "case screws",
        "thermal paste",
        "RAM slots",
        "PCIe slots"
    ]
    
    # Legacy descriptors
    LEGACIES = [
        "Pioneer of vintage mining",
        "Guardian of the old guard",
        "Champion of anti-obsolescence",
        "Warrior against e-waste",
        "Veteran of the silicon wars",
        "Legend of the RustChain"
    ]
    
    def __init__(self, style: str = "poetic"):
        """
        Initialize eulogy generator.
        
        Args:
            style: Eulogy style (poetic, technical, humorous, epic, random)
        """
        self.style = style
    
    def generate(self, data: EulogyData) -> str:
        """
        Generate a eulogy for the given miner data.
        
        Args:
            data: EulogyData with miner statistics
            
        Returns:
            Generated eulogy text
        """
        # Select style
        style = self.style
        if style == "random":
            style = random.choice(list(self.TEMPLATES.keys()))
        
        # Get templates for style
        templates = self.TEMPLATES.get(style, self.TEMPLATES["poetic"])
        template = random.choice(templates)
        
        # Build replacement data
        replacements = self._build_replacements(data)
        
        # Generate eulogy
        eulogy = template.format(**replacements)
        
        # Clean up whitespace
        eulogy = " ".join(eulogy.split())
        
        logger.debug(f"Generated {style} eulogy ({len(eulogy)} chars)")
        return eulogy
    
    def _build_replacements(self, data: EulogyData) -> Dict[str, str]:
        """Build template replacement dictionary."""
        # Calculate average multiplier
        avg_mult = sum(data.multiplier_history) / len(data.multiplier_history) if data.multiplier_history else 1.0
        
        # Get architecture-specific features
        arch_lower = data.device_arch.lower()
        unique_feature = next(
            (v for k, v in self.UNIQUE_FEATURES.items() if k in arch_lower),
            self.UNIQUE_FEATURES["default"]
        )
        
        # Format dates
        try:
            start_date = datetime.fromisoformat(data.first_attestation).strftime("%Y-%m-%d")
            end_date = datetime.fromisoformat(data.last_attestation).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            start_date = "Unknown"
            end_date = "Unknown"
        
        return {
            "device": data.device_model,
            "arch": data.device_arch,
            "epochs": f"{data.total_epochs:,}",
            "rtc": f"{data.total_rtc_earned:.2f}",
            "years": f"{data.years_of_service:.1f}",
            "days": data.days_inactive,
            "start": start_date,
            "end": end_date,
            "unique_feature": unique_feature,
            "survivor": random.choice(self.SURVIVORS),
            "component": random.choice(["processor", "motherboard", "silicon heart", "logic boards"]),
            "avg_mult": f"{avg_mult:.2f}",
            "legacy": random.choice(self.LEGACIES),
            "miner_id": data.miner_id[:16] + "..." if len(data.miner_id) > 16 else data.miner_id
        }
    
    def generate_all_styles(self, data: EulogyData) -> Dict[str, str]:
        """Generate eulogies in all styles for comparison."""
        results = {}
        original_style = self.style
        
        for style in self.TEMPLATES.keys():
            self.style = style
            results[style] = self.generate(data)
        
        self.style = original_style
        return results


def generate_sample_eulogy() -> str:
    """Generate a sample eulogy for demonstration."""
    sample_data = EulogyData(
        miner_id="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
        device_model="Power Mac G4 MDD",
        device_arch="PowerPC G4",
        total_epochs=847,
        total_rtc_earned=412.5,
        days_inactive=14,
        years_of_service=2.3,
        first_attestation="2023-10-15T08:30:00",
        last_attestation="2026-03-08T14:22:00",
        multiplier_history=[1.5, 1.5, 1.5, 1.5]
    )
    
    generator = EulogyGenerator(style="poetic")
    return generator.generate(sample_data)


if __name__ == "__main__":
    # Demo mode
    print("=== Silicon Obituary Eulogy Generator ===\n")
    print(generate_sample_eulogy())
