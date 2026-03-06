# flame_beacon.py
# Real FlameNet beacon: watches poa_event_log.json for new entries and dispatches to Discord

import json
import time
import requests
from datetime import datetime
from pathlib import Path

# === CONFIGURATION ===
EVENT_LOG_FILE = "poa_event_log.json"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/your_webhook_here"
JSON_HISTORY_FILE = "flame_history.json"

def load_events(path):
    try:
        with open(path, "r") as f:
            return [json.loads(line.strip()) for line in f if line.strip()]
    except FileNotFoundError:
        print("[⚠️] Event log not found.")
        return []
    except Exception as e:
        print(f"[❌] Error loading events: {e}")
        return []

def send_to_discord(entry):
    msg = (
        f"🔥 **FlameNet Beacon Broadcast** 🔥\n"
        f"[🕰️] `{entry['timestamp']}`\n"
        f"[💾] **Device**: {entry['device']}\n"
        f"[⚙️] **Score**: {entry['score']}\n"
        f"[📼] **ROM**: {entry['rom']}\n"
        f"[🔑] **ID**: `{entry['fingerprint'][:12]}...`"
    )
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"content": msg})
        if response.status_code == 204:
            print(f"[📡] Broadcasted: {entry['device']} ({entry['score']})")
        else:
            print(f"[⚠️] Discord response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[❌] Discord send failed: {e}")

def update_history(entry):
    try:
        history = []
        path = Path(JSON_HISTORY_FILE)
        if path.exists():
            with open(path, "r") as f:
                history = json.load(f)
        history.append(entry)
        with open(path, "w") as f:
            json.dump(history[-500:], f, indent=2)
    except Exception as e:
        print(f"[⚠️] Failed to update history: {e}")

def watch_beacon():
    print("[📡] Real FlameNet Beacon active...")
    seen = set()
    while True:
        entries = load_events(EVENT_LOG_FILE)
        for entry in entries:
            entry_id = entry.get("fingerprint")
            if not entry_id or entry_id in seen:
                continue
            seen.add(entry_id)
            if "timestamp" not in entry:
                entry["timestamp"] = datetime.utcnow().isoformat()
            send_to_discord(entry)
            update_history(entry)
        time.sleep(6)

if __name__ == "__main__":
    watch_beacon()
