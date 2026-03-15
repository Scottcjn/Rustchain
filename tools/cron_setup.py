#!/usr/bin/env python3
"""RustChain Cron Setup — Configure automated scheduled tasks."""
import os, sys, subprocess

JOBS = {
    "health_check": {"schedule": "*/5 * * * *", "cmd": "python3 {tools}/readiness_probe.py", "desc": "Health check every 5 min"},
    "backup": {"schedule": "0 2 * * *", "cmd": "python3 {tools}/backup/backup.py", "desc": "Daily backup at 2 AM"},
    "price_track": {"schedule": "*/15 * * * *", "cmd": "python3 {tools}/price_tracker.py", "desc": "Price tracking every 15 min"},
    "supply_track": {"schedule": "0 * * * *", "cmd": "python3 {tools}/supply_tracker.py", "desc": "Supply tracking hourly"},
    "snapshot": {"schedule": "0 */6 * * *", "cmd": "python3 {tools}/network_snapshot.py", "desc": "Network snapshot every 6h"},
}

def setup(tools_dir=None):
    tools_dir = tools_dir or os.path.dirname(os.path.abspath(__file__))
    print("RustChain Cron Setup\n" + "=" * 50)
    for name, job in JOBS.items():
        cmd = job["cmd"].format(tools=tools_dir)
        cron_line = f'{job["schedule"]} {cmd} >> ~/.rustchain/logs/cron_{name}.log 2>&1'
        print(f"  {name:<15} {job['desc']}")
        print(f"    {cron_line}")
    print(f"\nTo install, add these to crontab: crontab -e")

if __name__ == "__main__":
    setup()
