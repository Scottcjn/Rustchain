#!/usr/bin/env python3
"""
GPU and Display Detector

Detects vintage GPU and display hardware by scanning PCI device information
and awards corresponding relic badges for legacy hardware configurations.

Supported Badge Categories:
    GPU Badges:
        - Voodoo FX/G (3dfx Voodoo graphics cards)
        - Voodoo SLI (SLI configuration)
        - ATI Rage Pro
        - Matrox Ghost
        - PowerVR/Prophet
        - Amiga Warrior
    
    Display Badges:
        - Hercules Monochrome
        - CGA Experiment
        - XGA Rebel
        - VGA Ancestor

Platform Support:
    - Linux: Uses `lspci` command (requires pciutils package)
    - Windows/macOS: Not currently supported (lspci not available)

Example:
    >>> detect_gpu_and_display()
    Unlocked 2 badge(s): ['badge_voodoo_fx_g', 'badge_vga_ancestor']
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path


# GPU hardware detection flags and corresponding badge IDs
GPU_FLAGS: Dict[str, str] = {
    "voodoo": "badge_voodoo_fx_g",
    "sli": "badge_voodoo_sli",
    "ati rage": "badge_ati_rage_pro",
    "matrox": "badge_matrox_ghost",
    "powervr": "badge_powertile_prophet",
    "amiga": "badge_amiga_warrior",
}


# Display hardware detection flags and corresponding badge IDs
DISPLAY_FLAGS: Dict[str, str] = {
    "hercules": "badge_hercules_monochrome",
    "cga": "badge_cga_experiment",
    "xga": "badge_xga_rebel",
    "vga compatible": "badge_vga_ancestor",
}


def detect_gpu_and_display(output_file: str = "unlocked_badges.json") -> List[str]:
    """
    Detect vintage GPU and display hardware and award relic badges.
    
    Scans PCI device information using `lspci` command and searches for
    signatures of legacy graphics hardware. Awards badges for each detected
    vintage component.
    
    Args:
        output_file: Path to write unlocked badges JSON (default: "unlocked_badges.json")
        
    Returns:
        List of badge IDs that were unlocked
        
    Note:
        - Only works on Linux systems with lspci available
        - Requires pciutils package installed
        - Case-insensitive matching on PCI device strings
        
    Example:
        >>> badges = detect_gpu_and_display()
        >>> print(f"Unlocked {len(badges)} badges")
    """
    badges: List[str] = []
    
    # Try to get PCI device information
    try:
        output: str = subprocess.check_output(
            "lspci",
            shell=True,
            text=True,
            stderr=subprocess.DEVNULL
        ).decode().lower()
    except (subprocess.CalledProcessError, FileNotFoundError):
        # lspci not available or failed
        output = ""
    
    # Get current timestamp for badge metadata
    now: str = datetime.utcnow().isoformat() + "Z"
    
    # Search for GPU hardware signatures
    for flag, badge_id in GPU_FLAGS.items():
        if flag in output:
            badges.append(badge_id)
    
    # Search for display hardware signatures
    for flag, badge_id in DISPLAY_FLAGS.items():
        if flag in output:
            badges.append(badge_id)
    
    # Write results if any badges were unlocked
    if badges:
        badge_entries: List[Dict[str, Any]] = [
            {"badge_id": b, "awarded_at": now} for b in badges
        ]
        
        result: Dict[str, Any] = {"badges": badge_entries}
        
        # Write to output file
        output_path: Path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4)
        
        print(f"Unlocked {len(badges)} badge(s): {badges}")
    else:
        print("No relic badges detected.")
    
    return badges


def main() -> None:
    """Main entry point for GPU display detector."""
    detect_gpu_and_display()


if __name__ == "__main__":
    main()
