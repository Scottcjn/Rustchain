import platform
import subprocess
import json
from datetime import datetime

def detect_legacy_os_badges():
    detected_os = platform.system()
    badges = []

    simulated_os_data = {
        "DOS": ["autoexec.bat", "config.sys", "command.com"],
        "MacOS": ["System Folder", "Finder", "Macintosh HD"],
        "BeOS": ["beos", "/boot/beos", "tracker", "deskbar"],
        "Win3x": ["progman.exe", "win.ini", "winfile.exe"],
        "Win95": ["command.com", "start menu", "taskbar"]
    }

    badge_map = {
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

    detected_keywords = []
    try:
        output = subprocess.check_output("dir", shell=True).decode().lower()
        for system_key, terms in simulated_os_data.items():
            if any(term.lower() in output for term in terms):
                detected_keywords.append(system_key)
    except:
        pass

    for key in detected_keywords:
        badge = badge_map[key]
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

if __name__ == "__main__":
    output = detect_legacy_os_badges()
    with open("relic_rewards.json", "w") as f:
        json.dump(output, f, indent=4)
    print(f"Legacy OS badges awarded: {[b['title'] for b in output['badges']]}")
