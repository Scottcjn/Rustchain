#!/usr/bin/env python3
"""
BIOS Paw Paw Detector

Detects legacy hardware by reading BIOS release dates and awards the
"Paw Paw Legacy Miner" badge to miners using hardware from 1990 or earlier.

This module is part of the RustChain Proof of Antiquity (PoA) system,
which rewards miners for running validators on genuine vintage hardware.

Platform Support:
    - Windows: Uses WMIC to query BIOS release date
    - Linux: Uses dmidecode to read SMBIOS/DMI tables
    - macOS: Not supported (no standard BIOS)

Badge Details:
    - NFT ID: badge_pawpaw_legacy_miner
    - Class: Timeworn Relic
    - Rarity: Mythic (Soulbound)
    - Symbol: 🧓⌛

Example:
    >>> result = award_pawpaw_badge()
    >>> if result["badges"]:
    ...     print(f"Badge awarded for hardware from {result['badges'][0]['emotional_resonance']['trigger']}")
"""

import subprocess
import platform
import json
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path


def get_bios_date() -> Optional[datetime]:
    """
    Retrieve the system BIOS release date.
    
    Uses platform-specific commands to query BIOS information:
    - Windows: `wmic bios get releasedate`
    - Linux: `dmidecode -t bios` (requires root/sudo)
    
    Returns:
        datetime object if BIOS date successfully parsed, None otherwise
        
    Note:
        - Windows returns date in YYYYMMDD format
        - Linux returns date in MM/DD/YYYY format
        - Linux command requires root privileges for dmidecode access
        - macOS does not have a traditional BIOS, returns None
        
    Security Consideration:
        This function executes system commands. In production, consider
        using platform APIs instead of shell commands where available.
    """
    try:
        system = platform.system()
        
        if system == "Windows":
            # Windows: Query BIOS release date via WMIC
            output = subprocess.check_output(
                "wmic bios get releasedate",
                shell=True,
                text=True
            ).decode().splitlines()
            
            for line in output:
                line = line.strip()
                # WMIC returns date as YYYYMMDDHHMMSS.000000+XXX
                if line.isdigit() and len(line) >= 8:
                    date_str = line[:8]  # Extract YYYYMMDD
                    return datetime.strptime(date_str, "%Y%m%d")
                    
        elif system == "Linux":
            # Linux: Read BIOS date from DMI/SMBIOS tables
            output = subprocess.check_output(
                "dmidecode -t bios",
                shell=True,
                stderr=subprocess.DEVNULL,
                text=True
            ).decode().splitlines()
            
            for line in output:
                if "Release Date" in line:
                    # Format: "Release Date: MM/DD/YYYY"
                    date_str = line.split(":")[1].strip()
                    return datetime.strptime(date_str, "%m/%d/%Y")
                    
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
        # Silently fail - BIOS date not available or parsing failed
        pass
    
    return None


def award_pawpaw_badge(output_file: str = "relic_rewards.json") -> Dict[str, Any]:
    """
    Award Paw Paw Legacy Miner badge if BIOS date indicates vintage hardware (≤1990).
    
    Args:
        output_file: Path to write badge JSON results (default: "relic_rewards.json")
        
    Returns:
        Dict containing badges list (empty if no qualifying hardware detected)
        
    Badge Criteria:
        - BIOS release date must be 1990 or earlier
        - Represents genuine vintage hardware (386/486 era or earlier)
        
    Example:
        >>> result = award_pawpaw_badge()
        >>> if result["badges"]:
        ...     print("Paw Paw badge awarded for vintage hardware!")
        ...     print(f"Hardware from: {result['badges'][0]['emotional_resonance']['trigger']}")
    """
    bios_date = get_bios_date()
    
    # Check if BIOS date qualifies (1990 or earlier)
    if bios_date and bios_date.year <= 1990:
        badge: Dict[str, Any] = {
            "nft_id": "badge_pawpaw_legacy_miner",
            "title": "Back in My Day – Paw Paw Achievement",
            "class": "Timeworn Relic",
            "description": (
                "Awarded to miners who validate a RustChain block using "
                "hardware from 1990 or earlier."
            ),
            "emotional_resonance": {
                "state": "ancestral endurance",
                "trigger": f"BIOS dated {bios_date.strftime('%Y-%m-%d')}",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            },
            "symbol": "🧓⌛",
            "visual_anchor": "amber CRT over a dusty beige keyboard",
            "rarity": "Mythic",
            "soulbound": True
        }
        
        result = {"badges": [badge]}
        
        # Write results to file
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4)
        
        return result
    
    return {"badges": []}


if __name__ == "__main__":
    result = award_pawpaw_badge()
    
    # Write results to file
    output_path = Path("relic_rewards.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4)
    
    if result["badges"]:
        print("Paw Paw badge awarded.")
        print(f"Hardware detected from: {result['badges'][0]['emotional_resonance']['trigger']}")
    else:
        print("No qualifying BIOS date found (requires hardware from 1990 or earlier).")
