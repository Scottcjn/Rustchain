#!/usr/bin/env python3
"""RustChain Mining Calendar — Track daily mining activity."""
import json, os, sqlite3, time
from datetime import datetime, timedelta
DB = os.path.expanduser("~/.rustchain/mining_calendar.db")
def init():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS days (date TEXT PRIMARY KEY, epochs INT, rtc REAL, uptime REAL)")
    conn.commit()
    return conn
def record(epochs=0, rtc=0.0, uptime=100.0):
    conn = init()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    conn.execute("INSERT OR REPLACE INTO days VALUES (?,?,?,?)", (today, epochs, rtc, uptime))
    conn.commit()
    print(f"Recorded: {today} | {epochs} epochs | {rtc} RTC | {uptime}% uptime")
    conn.close()
def show(days=7):
    conn = init()
    rows = conn.execute("SELECT * FROM days ORDER BY date DESC LIMIT ?", (days,)).fetchall()
    print(f"Mining Calendar (last {days} days)")
    for date, epochs, rtc, uptime in rows:
        bar = "#" * int(uptime / 5)
        print(f"  {date} | {epochs:>3} epochs | {rtc:>8.4f} RTC | {bar}")
    conn.close()
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "record": record()
    else: show()
