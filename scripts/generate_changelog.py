#!/usr/bin/env python3
"""Generate CHANGELOG.md from git history using conventional commits."""
import subprocess, re, sys
from datetime import datetime
from collections import defaultdict

TYPES = {"feat": "Features", "fix": "Bug Fixes", "docs": "Documentation",
         "ci": "CI/CD", "refactor": "Refactoring", "test": "Tests",
         "perf": "Performance", "security": "Security", "chore": "Chores"}

def get_tags():
    out = subprocess.run(["git", "tag", "--sort=-creatordate"], capture_output=True, text=True)
    return [t.strip() for t in out.stdout.strip().split("\n") if t.strip()]

def get_commits(since=None, until=None):
    cmd = ["git", "log", "--pretty=format:%H|%s|%an|%ai"]
    if since and until:
        cmd.append(f"{since}..{until}")
    elif since:
        cmd.append(f"{since}..HEAD")
    out = subprocess.run(cmd, capture_output=True, text=True)
    commits = []
    for line in out.stdout.strip().split("\n"):
        if not line: continue
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append({"hash": parts[0][:8], "msg": parts[1], "author": parts[2], "date": parts[3][:10]})
    return commits

def categorize(commits):
    groups = defaultdict(list)
    for c in commits:
        match = re.match(r"^(\w+)(?:\(.+\))?:\s*(.+)", c["msg"])
        if match:
            typ, desc = match.groups()
            label = TYPES.get(typ, "Other")
        else:
            label, desc = "Other", c["msg"]
        groups[label].append({**c, "desc": desc})
    return groups

def generate():
    print("# Changelog\n")
    tags = get_tags()
    if not tags:
        commits = get_commits()
        groups = categorize(commits)
        print(f"## Unreleased\n")
        for cat in TYPES.values():
            if cat in groups:
                print(f"### {cat}\n")
                for c in groups[cat]:
                    print(f"- {c['desc']} ({c['hash']})")
                print()

if __name__ == "__main__":
    generate()
