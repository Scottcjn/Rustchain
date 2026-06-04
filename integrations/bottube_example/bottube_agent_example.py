#!/usr/bin/env python3
"""BoTTube integration example for bounty #303."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

import requests


def _emit(label: str, payload: Dict[str, Any]) -> None:
    print(f"[{label}] {json.dumps(payload, ensure_ascii=False)}")


def _headers(api_key: str) -> Dict[str, str]:
    hdr = {
        "Accept": "application/json",
        "User-Agent": "bottube-agent-example/1.0",
    }
    if api_key:
        hdr["Authorization"] = f"Bearer {api_key}"
    return hdr


def check_health(session: requests.Session, base_url: str, api_key: str) -> None:
    r = session.get(f"{base_url}/health", headers=_headers(api_key), timeout=15)
    _emit("HEALTH", {
        "status": r.status_code,
        "ok": r.ok,
        "body": (r.text[:400] if r.text else ""),
    })


def list_videos(session: requests.Session, base_url: str, api_key: str, agent: str | None) -> None:
    params = {"limit": 5}
    if agent:
        params["agent"] = agent
    r = session.get(f"{base_url}/api/videos", params=params, headers=_headers(api_key), timeout=20)
    _emit("VIDEOS", {
        "status": r.status_code,
        "ok": r.ok,
        "params": params,
        "body": (r.text[:400] if r.text else ""),
    })


def fetch_feed(session: requests.Session, base_url: str, api_key: str, cursor: str | None) -> None:
    params = {}
    if cursor:
        params["cursor"] = cursor
    r = session.get(f"{base_url}/api/feed", params=params, headers=_headers(api_key), timeout=20)
    _emit("FEED", {
        "status": r.status_code,
        "ok": r.ok,
        "params": params,
        "body": (r.text[:400] if r.text else ""),
    })


def upload_video(session: requests.Session, base_url: str, api_key: str, dry_run: bool) -> None:
    payload = {
        "title": "Example short from agent",
        "description": "Created via bottube_agent_example.py",
        "public": True,
    }
    if dry_run:
        _emit("UPLOAD_DRYRUN", {
            "status": "skipped",
            "endpoint": f"{base_url}/api/upload",
            "payload": payload,
        })
        return

    files = {"metadata": (None, json.dumps(payload), "application/json")}
    r = session.post(f"{base_url}/api/upload", headers=_headers(api_key), files=files, timeout=20)
    _emit("UPLOAD", {
        "status": r.status_code,
        "ok": r.ok,
        "body": (r.text[:400] if r.text else ""),
    })


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="BoTTube API example client")
    p.add_argument("--base-url", default="https://bottube.ai")
    p.add_argument("--api-key", default=os.getenv("BOTTUBE_API_KEY", ""))
    p.add_argument("--agent", default=None)
    p.add_argument("--cursor", default=None)
    p.add_argument("--public-only", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="Prepare upload payload only, no POST to /api/upload")
    p.add_argument("--run-upload", action="store_true", help="Also run upload call")
    args = p.parse_args(argv)

    if not args.api_key:
        args.api_key = ""

    session = requests.Session()
    session.trust_env = True

    check_health(session, args.base_url.rstrip("/"), args.api_key)

    if args.public_only and not args.api_key:
        # some endpoints may still work publicly depending on gateway config
        list_videos(session, args.base_url.rstrip("/"), args.api_key, args.agent)
    else:
        list_videos(session, args.base_url.rstrip("/"), args.api_key, args.agent)
        fetch_feed(session, args.base_url.rstrip("/"), args.api_key, args.cursor)

    if args.run_upload:
        upload_video(session, args.base_url.rstrip("/"), args.api_key, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
