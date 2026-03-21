"""
marketplace_ui — CLI tool for browsing and renting vintage machines.
Usage:
  python marketplace_ui.py list
  python marketplace_ui.py available --hours 4
  python marketplace_ui.py book --machine 0 --hours 1 --start <unix_ts> --renter <address>
  python marketplace_ui.py status --rental <rental_id>
  python marketplace_ui.py receipt --receipt <receipt_id>
  python marketplace_ui.py complete --rental <rental_id> --output <hash>
  python marketplace_ui.py leaderboard
"""
import argparse
import json
import sys
import time
import os
from pathlib import Path

# Add parent dir to path so we can import relic_market
sys.path.insert(0, str(Path(__file__).parent))

from machine_registry import MachineRegistry
from escrow import EscrowManager
from provenance_receipt import ProvenanceReceiptManager
from reservation_server import RESERVATIONS_DB, registry, escrow_mgr, receipt_mgr, _compute_available_slots, Reservation
import sqlite3


API_BASE = os.environ.get("RELIC_API_BASE", "http://localhost:5001")


def cmd_list(args):
    """List all machines in the registry."""
    machines = registry.list_machines(active_only=False)
    print(f"\n{'─'*70}")
    print(f"  {'TOKEN':<6} {'NAME':<20} {'MODEL':<25} {'RATE':<10} {'ACTIVE'}")
    print(f"{'─'*70}")
    for m in machines:
        print(f"  {m.token_id:<6} {m.name:<20} {m.model:<25} "
              f"{m.hourly_rate_rtc:<10.1f} {'✓' if m.is_active else '✗'}")
    print(f"{'─'*70}")
    print(f"Total machines: {len(machines)}")


def cmd_available(args):
    """Show available time slots for machines."""
    slot_hours = args.hours or 1
    machines = registry.list_machines(active_only=True)
    print(f"\nAvailable machines — {slot_hours}h slots")
    print(f"{'─'*70}")

    for m in machines:
        slots = _compute_available_slots(m.token_id, slot_hours)
        print(f"\n[{m.token_id}] {m.name} — {m.model}")
        print(f"  Rate: {m.hourly_rate_rtc} RTC/hr | Uptime: {m.uptime_formatted} | Rentals: {m.total_rentals}")
        print(f"  Specs: {json.dumps(m.specs)}")
        if slots:
            print(f"  Next slots ({len(slots)} shown of total):")
            for s in slots[:5]:
                print(f"    {s['start_iso']} → {s['end_iso']}")
        else:
            print("  No slots available in next 7 days")
    print(f"{'─'*70}")


def cmd_book(args):
    """Book a machine via direct API call."""
    import urllib.request, urllib.parse

    if not args.renter:
        print("Error: --renter address required")
        return

    payload = json.dumps({
        "machine_token_id": args.machine,
        "slot_hours": args.hours or 1,
        "start_time": args.start or time.time() + 300,  # 5 min from now if not specified
        "renter": args.renter,
    }).encode()

    req = urllib.request.Request(
        f"{API_BASE}/relic/reserve",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            print(f"\n✓ Reservation created!")
            print(f"  Rental ID:  {data['rental_id']}")
            print(f"  Escrow ID:  {data['escrow_id']}")
            print(f"  Machine:    {data['machine_name']}")
            print(f"  Start:      {data['start_time_iso']}")
            print(f"  End:        {data['end_time_iso']}")
            print(f"  RTC Locked: {data['rtc_locked']}")
            print(f"  State:      {data['state']}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Error {e.code}: {body}")
    except Exception as e:
        print(f"Connection error (is server running?): {e}")
        print("Falling back to direct DB simulation...")
        # Fallback: simulate locally
        _simulate_booking(args)


def _simulate_booking(args):
    """Fallback booking when server is not running."""
    machine = registry.get_machine(args.machine)
    if not machine:
        print(f"Machine {args.machine} not found")
        return
    slot_hours = args.hours or 1
    start_time = args.start or time.time() + 300
    end_time = start_time + slot_hours * 3600
    rtc_locked = machine.hourly_rate_rtc * slot_hours
    rental_id = f"rental_simu{time.time():.0f}"
    print(f"\n[SIMULATED] Booking: {machine.name} for {slot_hours}h at {start_time}")
    print(f"  RTC to lock: {rtc_locked}")


def cmd_status(args):
    """Check status of a reservation."""
    if not args.rental:
        print("Error: --rental required")
        return
    with sqlite3.connect(RESERVATIONS_DB) as conn:
        row = conn.execute(
            "SELECT * FROM reservations WHERE rental_id = ?", (args.rental,)
        ).fetchone()
    if not row:
        print("Rental not found")
        return
    res = Reservation(*row)
    machine = registry.get_machine(res.machine_token_id)
    print(f"\nRental: {res.rental_id}")
    print(f"  Machine:      {machine.name if machine else res.machine_token_id}")
    print(f"  Renter:       {res.renter}")
    print(f"  Slot:         {res.slot_hours}h")
    print(f"  Start:        {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(res.start_time))}")
    print(f"  End:          {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(res.end_time))}")
    print(f"  RTC Locked:   {res.rtc_locked}")
    print(f"  Escrow ID:    {res.escrow_id}")
    print(f"  State:        {res.state}")


def cmd_complete(args):
    """Complete a rental and generate provenance receipt."""
    if not args.rental:
        print("Error: --rental required")
        return

    with sqlite3.connect(RESERVATIONS_DB) as conn:
        row = conn.execute(
            "SELECT * FROM reservations WHERE rental_id = ?", (args.rental,)
        ).fetchone()
    if not row:
        print("Rental not found")
        return
    res = Reservation(*row)

    machine = registry.get_machine(res.machine_token_id)
    output_hash = args.output or f"output_hash_{res.rental_id}"
    attestation = args.attestation or "cpu_cycles=12345678,instruction_count=99999999,mem_access=5000000"

    receipt = receipt_mgr.create_receipt(
        machine_passport_id=machine.name if machine else str(res.machine_token_id),
        machine_model=machine.model if machine else "Unknown",
        session_id=res.rental_id,
        renter=res.renter,
        slot_hours=res.slot_hours,
        start_time=res.start_time,
        end_time=res.end_time,
        output_hash=output_hash,
        attestation_proof=attestation,
    )

    escrow_mgr.release(res.escrow_id, f"tx_{res.rental_id}")
    with sqlite3.connect(RESERVATIONS_DB) as conn:
        conn.execute("UPDATE reservations SET state = ? WHERE rental_id = ?",
                     ("completed", res.rental_id))
        conn.commit()

    print(f"\n✓ Session completed!")
    print(f"  Receipt ID:    {receipt.receipt_id}")
    print(f"  Machine:      {receipt.machine_passport_id}")
    print(f"  Output hash:  {receipt.output_hash}")
    print(f"  Signed at:    {receipt.signed_at_iso}")
    print(f"  Signature:    {receipt.signature[:32]}...")
    print(f"  Verified:     {receipt.verify()}")


def cmd_receipt(args):
    """Fetch and display a receipt."""
    if not args.receipt:
        print("Error: --receipt required")
        return
    receipt = receipt_mgr.get_receipt(args.receipt)
    if not receipt:
        print("Receipt not found")
        return
    print(f"\n{'═'*60}")
    print(f"  PROVENANCE RECEIPT — {receipt.machine_passport_id}")
    print(f"{'═'*60}")
    print(f"  Receipt ID:      {receipt.receipt_id}")
    print(f"  Session ID:     {receipt.session_id}")
    print(f"  Machine Model:  {receipt.machine_model}")
    print(f"  Renter:         {receipt.renter}")
    print(f"  Slot:           {receipt.slot_hours}h")
    print(f"  Duration:       {receipt.duration_seconds}s")
    print(f"  Start:          {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(receipt.start_time))}")
    print(f"  End:            {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(receipt.end_time))}")
    print(f"  Output Hash:    {receipt.output_hash}")
    print(f"  Attestation:    {receipt.attestation_proof}")
    print(f"  Ed25519 Pubkey: {receipt.ed25519_pubkey[:32]}...")
    print(f"  Signature:      {receipt.signature[:32]}...")
    print(f"  Signed At:      {receipt.signed_at_iso}")
    print(f"  Verified:       {'✓ PASS' if receipt.verify() else '✗ FAIL'}")
    print(f"{'═'*60}")


def cmd_leaderboard(args):
    """Show most-rented machines leaderboard."""
    machines = registry.list_machines(active_only=False)
    ranked = sorted(machines, key=lambda m: m.total_rentals, reverse=True)
    print(f"\n{'─'*60}")
    print(f"  {'RANK':<6} {'NAME':<20} {'MODEL':<20} {'RENTALS':<10} {'UPTIME'}")
    print(f"{'─'*60}")
    for i, m in enumerate(ranked, 1):
        print(f"  {i:<6} {m.name:<20} {m.model:<20} {m.total_rentals:<10} {m.uptime_formatted}")
    print(f"{'─'*60}")


def cmd_escrow_summary(args):
    """Show escrow state."""
    summary = escrow_mgr.summary()
    print(f"\nEscrow Summary")
    print(f"  Total locked RTC: {summary['total_locked_rtc']}")
    print(f"  Active escrows:   {summary['active_escrows']}")
    print(f"  Released:          {summary['released_count']}")
    print(f"  Refunded:          {summary['refunded_count']}")


def main():
    parser = argparse.ArgumentParser(description="RustChain Relic Market CLI")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="List all machines")
    sub.add_parser("available", help="Show available slots")
    sub.add_parser("leaderboard", help="Most-rented machines")
    sub.add_parser("escrow", help="Escrow summary")

    p_book = sub.add_parser("book", help="Book a machine")
    p_book.add_argument("--machine", type=int, required=True)
    p_book.add_argument("--hours", type=int, default=1)
    p_book.add_argument("--start", type=float, help="Unix timestamp for start")
    p_book.add_argument("--renter", type=str, required=True)

    p_status = sub.add_parser("status", help="Check reservation status")
    p_status.add_argument("--rental", type=str, required=True)

    p_complete = sub.add_parser("complete", help="Complete a rental")
    p_complete.add_argument("--rental", type=str, required=True)
    p_complete.add_argument("--output", type=str, help="Output hash")
    p_complete.add_argument("--attestation", type=str, help="Attestation proof")

    p_receipt = sub.add_parser("receipt", help="Show a receipt")
    p_receipt.add_argument("--receipt", type=str, required=True)

    args = parser.parse_args()

    if args.cmd == "list":
        cmd_list(args)
    elif args.cmd == "available":
        cmd_available(args)
    elif args.cmd == "book":
        cmd_book(args)
    elif args.cmd == "status":
        cmd_status(args)
    elif args.cmd == "complete":
        cmd_complete(args)
    elif args.cmd == "receipt":
        cmd_receipt(args)
    elif args.cmd == "leaderboard":
        cmd_leaderboard(args)
    elif args.cmd == "escrow":
        cmd_escrow_summary(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
