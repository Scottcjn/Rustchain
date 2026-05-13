import subprocess
import platform
import json
from datetime import datetime


def _run_hardware_query(args):
    return subprocess.check_output(
        args,
        stderr=subprocess.DEVNULL,
        timeout=10,
    ).decode().splitlines()


def get_bios_date():
    try:
        if platform.system() == "Windows":
            output = _run_hardware_query(["wmic", "bios", "get", "releasedate"])
            for line in output:
                date_str = line.strip()
                if len(date_str) >= 8 and date_str[:8].isdigit():
                    return datetime.strptime(date_str[:8], "%Y%m%d")
        elif platform.system() == "Linux":
            output = _run_hardware_query(["dmidecode", "-t", "bios"])
            for line in output:
                if "Release Date" in line:
                    date_str = line.split(":")[1].strip()
                    return datetime.strptime(date_str, "%m/%d/%Y")
    except:
        pass
    return None

def award_pawpaw_badge():
    bios_date = get_bios_date()
    if bios_date and bios_date.year <= 1990:
        badge = {
            "nft_id": "badge_pawpaw_legacy_miner",
            "title": "Back in My Day – Paw Paw Achievement",
            "class": "Timeworn Relic",
            "description": "Awarded to miners who validate a RustChain block using hardware from 1990 or earlier.",
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
        return {"badges": [badge]}
    return {"badges": []}

if __name__ == "__main__":
    result = award_pawpaw_badge()
    with open("relic_rewards.json", "w") as f:
        json.dump(result, f, indent=4)
    if result["badges"]:
        print("Paw Paw badge awarded.")
    else:
        print("No qualifying BIOS date found.")
