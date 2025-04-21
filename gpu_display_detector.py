import json
import platform
import subprocess
from datetime import datetime

def detect_gpu_and_display():
    badges = []

    try:
        output = subprocess.check_output("lspci", shell=True).decode().lower()
    except Exception:
        output = ""

    gpu_flags = {
        "voodoo": "badge_voodoo_fx_g",
        "sli": "badge_voodoo_sli",
        "ati rage": "badge_ati_rage_pro",
        "matrox": "badge_matrox_ghost",
        "powervr": "badge_powertile_prophet",
        "amiga": "badge_amiga_warrior",
    }

    display_flags = {
        "hercules": "badge_hercules_monochrome",
        "cga": "badge_cga_experiment",
        "xga": "badge_xga_rebel",
        "vga compatible": "badge_vga_ancestor",
    }

    now = datetime.utcnow().isoformat() + "Z"

    # Search GPU indicators
    for key, badge_id in gpu_flags.items():
        if key in output:
            badges.append(badge_id)

    # Search Display indicators
    for key, badge_id in display_flags.items():
        if key in output:
            badges.append(badge_id)

    if badges:
        badge_entries = [{"badge_id": b, "awarded_at": now} for b in badges]
        with open("unlocked_badges.json", "w") as f:
            json.dump({"badges": badge_entries}, f, indent=4)
        print(f"Unlocked {len(badges)} badge(s):", [b for b in badges])
    else:
        print("No relic badges detected.")

if __name__ == "__main__":
    detect_gpu_and_display()
