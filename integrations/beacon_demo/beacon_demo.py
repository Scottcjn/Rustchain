"""Beacon integration demo for RustChain bounty #158.

Safe by default:
- Uses loopback UDP unless you override host/bind.
- Writes demo state only under integrations/beacon_demo/.state.
- Does not create or store any RustChain wallet keys.

Requires: pip install beacon-skill
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from beacon_skill import AgentIdentity, HeartbeatManager
from beacon_skill.codec import encode_envelope, decode_envelopes, verify_envelope
from beacon_skill.contracts import ContractManager
from beacon_skill.transports.udp import udp_listen, udp_send


STATE_DIR = Path(__file__).resolve().parent / ".state"


def _print(obj) -> None:
    sys.stdout.write(json.dumps(obj, sort_keys=True) + "\n")
    sys.stdout.flush()


def cmd_listen(args) -> int:
    bind_host = args.bind
    port = int(args.port)
    timeout_s = float(args.timeout) if args.timeout is not None else None

    seen = {"count": 0}

    def on_msg(m):
        envs = decode_envelopes(m.text or "")
        verified = None
        if envs:
            # Prefer embedded pubkey verification.
            verified = verify_envelope(envs[0], known_keys=None)
        seen["count"] += 1
        _print(
            {
                "event": "udp_message",
                "from": f"{m.addr[0]}:{m.addr[1]}",
                "bytes": len(m.data),
                "verified": verified,
                "envelopes": envs,
            }
        )

    udp_listen(bind_host, port, on_msg, timeout_s=timeout_s)

    _print({"event": "listen_done", "count": seen["count"]})
    return 0


def cmd_send_heartbeat(args) -> int:
    host = args.host
    port = int(args.port)

    ident = AgentIdentity.generate(use_mnemonic=False)

    # Keep state in-repo.
    hb = HeartbeatManager(data_dir=STATE_DIR)
    payload = hb.build_heartbeat(
        ident,
        status=args.status,
        health={"demo": True, "ts": int(time.time())},
        config={"beacon": {"agent_name": "rustchain-beacon-demo"}, "_start_ts": int(time.time())},
    )

    envelope = encode_envelope(payload, version=2, identity=ident, include_pubkey=True)
    udp_send(host, port, envelope.encode("utf-8"), broadcast=bool(args.broadcast))

    _print(
        {
            "event": "heartbeat_sent",
            "host": host,
            "port": port,
            "agent_id": ident.agent_id,
            "envelope": envelope,
        }
    )
    return 0


def cmd_contracts_demo(_args) -> int:
    data_dir = STATE_DIR / "contracts"
    cm = ContractManager(data_dir=str(data_dir))

    # Use agent_id-like strings for seller/buyer for the demo.
    seller = "bcn_demo_seller"
    buyer = "bcn_demo_buyer"

    listed = cm.list_agent(agent_id=seller, contract_type="rent", price_rtc=1.25, duration_days=1, capabilities=["heartbeat", "contracts"], terms={"note": "demo"})
    if "error" in listed:
        _print({"event": "contracts_error", "step": "list_agent", "data": listed})
        return 2

    cid = listed["contract_id"]
    offered = cm.make_offer(cid, buyer_id=buyer, offered_price_rtc=1.25, message="demo offer")
    accepted = cm.accept_offer(cid)
    funded = cm.fund_escrow(cid, from_address="RTC_demo_funder", amount_rtc=1.25, tx_ref="demo_tx")
    active = cm.activate(cid)
    settled = cm.settle(cid)

    _print(
        {
            "event": "contracts_demo_done",
            "contract_id": cid,
            "listed": listed,
            "offered": offered,
            "accepted": accepted,
            "funded": funded,
            "active": active,
            "settled": settled,
        }
    )
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="beacon_demo")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("listen", help="Listen for UDP beacons and verify v2 envelopes")
    pl.add_argument("--bind", default="127.0.0.1")
    pl.add_argument("--port", default="38400")
    pl.add_argument("--timeout", type=float, default=8.0)
    pl.set_defaults(func=cmd_listen)

    ps = sub.add_parser("send-heartbeat", help="Send a signed heartbeat envelope over UDP")
    ps.add_argument("--host", default="127.0.0.1")
    ps.add_argument("--port", default="38400")
    ps.add_argument("--status", default="alive", choices=["alive", "degraded", "shutting_down"])
    ps.add_argument("--broadcast", action="store_true")
    ps.set_defaults(func=cmd_send_heartbeat)

    pc = sub.add_parser("contracts-demo", help="Run a local contracts lifecycle demo")
    pc.set_defaults(func=cmd_contracts_demo)

    args = p.parse_args(argv)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
