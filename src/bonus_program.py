import json
import os
from datetime import datetime
from typing import Dict, List, Optional

# ===== Bonus Configuration =====
BONUS_CONFIG = {
    "miner": {
        "first_attestation": 10,
        "real_hardware": 5,
        "vintage_hardware": 10
    },
    "developer": {
        "first_pr_merged": 25,
        "first_bounty_completed": 10
    },
    "referral": {
        "refer_miner": 10,
        "refer_dev": 15
    }
}

class BonusManager:
    def __init__(self, data_file: str = "claims.json"):
        self.data_file = data_file
        self.claims: Dict[str, dict] = {}
        self._load_claims()

    def _load_claims(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, "r") as f:
                self.claims = json.load(f)

    def _save_claims(self):
        with open(self.data_file, "w") as f:
            json.dump(self.claims, f, indent=2)

    def _wallet_exists(self, wallet: str) -> bool:
        return wallet in self.claims

    def _register_wallet(self, wallet: str, wallet_type: str):
        self.claims[wallet] = {
            "type": wallet_type,
            "created_at": datetime.utcnow().isoformat(),
            "first_attestation": False,
            "real_hardware": False,
            "vintage_hardware": False,
            "first_pr_merged": False,
            "first_bounty_completed": False,
            "referrals": []
        }

    def claim_miner_bonus(self, wallet: str, hardware_type: str = "standard") -> Optional[int]:
        if self._wallet_exists(wallet):
            return None  # Already claimed some bonus
        
        amount = BONUS_CONFIG["miner"]["first_attestation"]
        if hardware_type == "real":
            amount += BONUS_CONFIG["miner"]["real_hardware"]
        elif hardware_type == "vintage":
            amount += BONUS_CONFIG["miner"]["vintage_hardware"]
        
        self._register_wallet(wallet, "miner")
        self.claims[wallet]["first_attestation"] = True
        if hardware_type == "real":
            self.claims[wallet]["real_hardware"] = True
        elif hardware_type == "vintage":
            self.claims[wallet]["vintage_hardware"] = True
        
        self._save_claims()
        return amount

    def claim_dev_bonus(self, wallet: str, bonus_type: str = "first_pr") -> Optional[int]:
        if self._wallet_exists(wallet):
            return None
        
        amount = 0
        if bonus_type == "first_pr":
            amount = BONUS_CONFIG["developer"]["first_pr_merged"]
            self._register_wallet(wallet, "developer")
            self.claims[wallet]["first_pr_merged"] = True
        elif bonus_type == "first_bounty":
            amount = BONUS_CONFIG["developer"]["first_bounty_completed"]
            self._register_wallet(wallet, "developer")
            self.claims[wallet]["first_bounty_completed"] = True
        else:
            return None
        
        self._save_claims()
        return amount

    def claim_referral_bonus(self, referrer: str, new_user: str, referral_type: str) -> Optional[int]:
        if not self._wallet_exists(new_user):
            return None  # New user must have at least one bonus
        if self._wallet_exists(referrer):
            if new_user in self.claims[referrer].get("referrals", []):
                return None  # Already referred this user
        else:
            self._register_wallet(referrer, "referrer")
        
        if referral_type == "miner":
            amount = BONUS_CONFIG["referral"]["refer_miner"]
        elif referral_type == "dev":
            amount = BONUS_CONFIG["referral"]["refer_dev"]
        else:
            return None
        
        self.claims[referrer]["referrals"].append(new_user)
        self._save_claims()
        return amount

    def get_wallet_bonus_total(self, wallet: str) -> int:
        if not self._wallet_exists(wallet):
            return 0
        total = 0
        w = self.claims[wallet]
        if w["first_attestation"]:
            total += BONUS_CONFIG["miner"]["first_attestation"]
            if w["real_hardware"]:
                total += BONUS_CONFIG["miner"]["real_hardware"]
            if w["vintage_hardware"]:
                total += BONUS_CONFIG["miner"]["vintage_hardware"]
        if w["first_pr_merged"]:
            total += BONUS_CONFIG["developer"]["first_pr_merged"]
        if w["first_bounty_completed"]:
            total += BONUS_CONFIG["developer"]["first_bounty_completed"]
        # Referral bonuses not tracked per wallet in this simple version
        return total


if __name__ == "__main__":
    import sys
    manager = BonusManager()
    if len(sys.argv) < 3:
        print("Usage: python bonus_program.py <action> <wallet> [params]")
        sys.exit(1)
    action = sys.argv[1]
    wallet = sys.argv[2]
    if action == "claim_miner":
        hw = sys.argv[3] if len(sys.argv) > 3 else "standard"
        amount = manager.claim_miner_bonus(wallet, hw)
        if amount:
            print(f"Claimed {amount} RTC!")
        else:
            print("Wallet already claimed or invalid.")
    elif action == "claim_dev":
        bt = sys.argv[3] if len(sys.argv) > 3 else "first_pr"
        amount = manager.claim_dev_bonus(wallet, bt)
        if amount:
            print(f"Claimed {amount} RTC!")
        else:
            print("Wallet already claimed or invalid.")
    elif action == "refer":
        if len(sys.argv) < 5:
            print("Usage: refer <referrer> <new_user> <type>")
            sys.exit(1)
        new_user = sys.argv[3]
        ref_type = sys.argv[4]
        amount = manager.claim_referral_bonus(wallet, new_user, ref_type)
        if amount:
            print(f"Claimed {amount} RTC for referral!")
        else:
            print("Referral invalid or already claimed.")
    elif action == "balance":
        total = manager.get_wallet_bonus_total(wallet)
        print(f"Total bonuses for {wallet}: {total} RTC")
    else:
        print("Unknown action.")
