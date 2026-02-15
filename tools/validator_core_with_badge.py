import json
import hashlib
from datetime import datetime

def simulate_entropy_score(cpu_model, bios_date):
    year = int(bios_date.split("-")[0])
    age_weight = max(0, 2025 - year)
    entropy_score = round((age_weight * 0.25) + (len(cpu_model) * 0.05), 2)
    return entropy_score

def generate_validator_entry():
    cpu_model = "Pentium III"
    bios_date = "1998-12-01"
    entropy = simulate_entropy_score(cpu_model, bios_date)
    fingerprint = hashlib.sha256(f"{cpu_model}_{bios_date}".encode()).hexdigest()

    validator_data = {
        "wallet": "example-wallet-123",
        "bios_timestamp": bios_date,
        "cpu_model": cpu_model,
        "entropy_score": entropy,
        "bios_fingerprint": fingerprint,
        "score_composite": round(entropy + 5.67, 2),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "rarity_bonus": 1.02
    }

    with open("proof_of_antiquity.json", "w") as f:
        json.dump(validator_data, f, indent=4)
    
    print("Validator proof_of_antiquity.json created.")

    # Link NFT badge if conditions are met
    if entropy >= 3.0:
        badge = {
            "nft_id": "badge_defrag_001",
            "title": "Automated Janitor – Pinesol Protocol",
            "class": "Utility Relic",
            "description": "Awarded to relic nodes that perform defrag operations or maintenance validations during mining cycles. Recognized for digital hygiene and entropy stabilization.",
            "emotional_resonance": {
                "state": "cleansed clarity",
                "trigger": "Defrag completed during mining",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            },
            "symbol": "🧼",
            "visual_anchor": "robot janitor with retro vacuum and pinesol bottle",
            "rarity": "Uncommon",
            "soulbound": True
        }

        with open("relic_rewards.json", "w") as b:
            json.dump({"badges": [badge]}, b, indent=4)
        print("NFT badge unlocked and written to relic_rewards.json.")

if __name__ == "__main__":
    generate_validator_entry()
