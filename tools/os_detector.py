#!/usr/bin/env python3
"""
Legacy OS Badge Detector

Detects legacy operating system environments (DOS, MacOS Classic, BeOS, Windows 3.x/95)
by scanning for characteristic files and directories. Awards NFT-style badges for
each detected legacy OS environment.

Badge Categories:
    - DOS Cowboy: DOS shell or COM boot detected
    - MacInitiate: System Folder and Apple Menu detected
    - BeOS Sleeper: BeOS or Haiku shell detected
    - Progman Pioneer: Windows 3.x Program Manager activity
    - Explorer Awakener: Windows 95 Start Menu / Desktop boot

Usage:
    python3 os_detector.py

Output:
    Creates relic_rewards.json with detected badges in current directory.
"""

import platform
import subprocess
import json
from datetime import datetime
from typing import Any, Dict, List


def detect_legacy_os_badges() -> Dict[str, List[Dict[str, Any]]]:
    """
    Detect legacy operating system environments and award commemorative badges.
    
    Scans current directory for files/directories characteristic of legacy OS
    environments (DOS, MacOS Classic, BeOS, Windows 3.x/95). Returns badge data
    for each detected environment.
    
    Returns:
        Dictionary with "badges" key containing list of badge dictionaries.
        Each badge includes nft_id, title, description, rarity, and metadata.
    
    Note:
        - Uses Windows `dir` command for file detection
        - Case-insensitive matching
        - Empty badges list if no legacy OS markers found
    """
    detected_os: str = platform.system()  # Current OS (for reference)
    badges: List[Dict[str, Any]] = []

    # Legacy OS file/directory signatures
    simulated_os_data: Dict[str, List[str]] = {
        "DOS": ["autoexec.bat", "config.sys", "command.com"],
        "MacOS": ["System Folder", "Finder", "Macintosh HD"],
        "BeOS": ["beos", "/boot/beos", "tracker", "deskbar"],
        "Win3x": ["progman.exe", "win.ini", "winfile.exe"],
        "Win95": ["command.com", "start menu", "taskbar"]
    }

    # Badge metadata for each OS
    badge_map: Dict[str, Dict[str, str]] = {
        "DOS": {
            "nft_id": "badge_dos_cowboy",
            "title": "DOS Cowboy",
            "trigger": "DOS shell or COM boot detected"
        },
        "MacOS": {
            "nft_id": "badge_macinitiate",
            "title": "MacInitiate",
            "trigger": "System Folder and Apple Menu detected"
        },
        "BeOS": {
            "nft_id": "badge_beos_sleeper",
            "title": "BeOS Sleeper",
            "trigger": "BeOS or Haiku shell detected"
        },
        "Win3x": {
            "nft_id": "badge_progman_pioneer",
            "title": "Progman Pioneer",
            "trigger": "Windows 3.x Program Manager activity"
        },
        "Win95": {
            "nft_id": "badge_explorer_awakener",
            "title": "Explorer Awakener",
            "trigger": "Windows 95 Start Menu / Desktop boot"
        }
    }

    # Scan directory for legacy OS markers
    detected_keywords: List[str] = []
    try:
        output: str = subprocess.check_output("dir", shell=True).decode().lower()
        for system_key, terms in simulated_os_data.items():
            if any(term.lower() in output for term in terms):
                detected_keywords.append(system_key)
    except Exception:
        pass  # Silent failure if dir command fails

    # Build badge objects for each detected OS
    for key in detected_keywords:
        badge: Dict[str, str] = badge_map[key]
        badges.append({
            "nft_id": badge["nft_id"],
            "title": badge["title"],
            "class": "OS Relic",
            "description": f"Awarded for running or emulating {key} environment.",
            "emotional_resonance": {
                "state": "boot memory echo",
                "trigger": badge["trigger"],
                "timestamp": datetime.utcnow().isoformat() + "Z"
            },
            "symbol": "💾🧠",
            "visual_anchor": f"{key} startup interface glow",
            "rarity": "Legendary" if key in ["MacOS", "Win3x"] else "Epic",
            "soulbound": True
        })

    return {"badges": badges}

def main() -> None:
    """
    Main entry point for OS detector script.
    
    Flow:
        1. Call detect_legacy_os_badges() to scan for legacy OS markers
        2. Write results to relic_rewards.json
        3. Print summary of awarded badges to stdout
    """
    output: Dict[str, List[Dict[str, Any]]] = detect_legacy_os_badges()
    
    # Save badge data to JSON file
    with open("relic_rewards.json", "w") as f:
        json.dump(output, f, indent=4)
    
    # Print summary
    badge_titles: List[str] = [b['title'] for b in output['badges']]
    print(f"Legacy OS badges awarded: {badge_titles}")


if __name__ == "__main__":
    main()
