#!/usr/bin/env python3
"""RustChain Event Logger — Structured event logging for node operations."""
import json, os, time, sys
from datetime import datetime

LOG_DIR = os.path.expanduser("~/.rustchain/events")

def log_event(event_type, data, severity="info"):
    os.makedirs(LOG_DIR, exist_ok=True)
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "type": event_type,
        "severity": severity,
        "data": data,
    }
    fname = datetime.utcnow().strftime("%Y-%m-%d") + ".jsonl"
    with open(os.path.join(LOG_DIR, fname), "a") as f:
        f.write(json.dumps(event) + "\n")
    return event

def query_events(date=None, event_type=None, severity=None):
    date = date or datetime.utcnow().strftime("%Y-%m-%d")
    fname = os.path.join(LOG_DIR, f"{date}.jsonl")
    if not os.path.exists(fname): return []
    events = []
    with open(fname) as f:
        for line in f:
            e = json.loads(line)
            if event_type and e["type"] != event_type: continue
            if severity and e["severity"] != severity: continue
            events.append(e)
    return events

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "query":
        for e in query_events():
            print(f"  [{e['severity']:>5}] {e['timestamp'][:19]} {e['type']}: {json.dumps(e['data'])[:60]}")
    else:
        e = log_event("test", {"message": "Event logger test"})
        print(f"Logged: {json.dumps(e, indent=2)}")
