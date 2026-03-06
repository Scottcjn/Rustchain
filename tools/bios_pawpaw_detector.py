import subprocess
import platform
import json
from datetime import datetime

def get_bios_date():
    try:
        if platform.system() == "Windows":
            output = subprocess.check_output("wmic bios get releasedate", shell=True).decode().splitlines()
            for line in output:
                if line.strip().isdigit() and len(line.strip()) >= 8:
                    date_str = line.strip()
                    return datetime.strptime(date_str[:8], "%Y%m%d")
        elif platform.system() == "Linux":
            output = subprocess.check_output("dmidecode -t bios", shell=True, stderr=subprocess.DEVNULL).decode().splitlines()
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
