# poa_sync_watcher.py
# Watches for PoA validation events and logs them to CSV and JSON (relay mode)

import json
import time
from datetime import datetime
from pathlib import Path

# Simulated source file from PoA API or TCP relay
WATCH_FILE = "poa_event_log.json"  # Can be replaced with tail -f or direct socket parsing
CSV_LOG = "relay_log.csv"
JSON_HISTORY = "flame_history.json"

def load_event_stream(path):
    try:
        with open(path, "r") as f:
            lines = f.readlines()
        return [json.loads(line.strip()) for line in lines if line.strip()]
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as e:
        print(f"[!] Bad JSON: {e}")
        return []

def append_csv(entry):
    with open(CSV_LOG, "a") as f:
        f.write(f"{entry['timestamp']},{entry['device']},{entry['score']},{entry.get('rom','')},{entry['fingerprint'][:10]}...\n")

def update_history(entry):
    history = []
    path = Path(JSON_HISTORY)
    if path.exists():
        with open(path) as f:
            try:
                history = json.load(f)
            except:
                history = []

    history.append(entry)
    with open(path, "w") as f:
        json.dump(history[-500:], f, indent=2)  # Keep last 500

def run_watcher():
    print("[🛰️] Watching for incoming PoA submissions...")
    seen_hashes = set()

    while True:
        entries = load_event_stream(WATCH_FILE)

        for entry in entries:
            entry_id = entry.get("fingerprint")
            if not entry_id or entry_id in seen_hashes:
                continue

            seen_hashes.add(entry_id)
            entry["timestamp"] = datetime.utcnow().isoformat()

            print(f"[🔥] {entry['device']} scored {entry['score']} → {entry_id[:8]}...")
            append_csv(entry)
            update_history(entry)

        time.sleep(5)

if __name__ == "__main__":
    run_watcher()
