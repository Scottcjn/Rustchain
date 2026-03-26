#!/usr/bin/env python3
"""
Beacon Dashboard v1.1 — Live Transport Traffic Monitor (TUI)

A curses-based terminal UI for monitoring Beacon transport traffic in real-time.
Reads beacon_envelopes from the RustChain SQLite database.

Usage:
    python beacon_dashboard.py
    python beacon_dashboard.py --db /path/to/rustchain_v2.db
    python beacon_dashboard.py --refresh 5 --no-sound

Keys:
    /       Enter filter mode
    Esc     Clear filter / exit
    e       Export CSV snapshot
    j       Export JSON snapshot
    s       Toggle sound alerts
    t       Cycle transport tab
    r       Force refresh
    q       Quit
    ↑/↓     Scroll envelope list
"""

import argparse
import curses
import os
import sys
import time

# Add package to path
sys.path.insert(0, os.path.dirname(__file__))

from dashboard_helpers import (
    DEFAULT_DB_PATH,
    apply_filter,
    check_alerts,
    compute_top_agents,
    compute_transport_health,
    export_csv,
    export_json,
    fetch_recent_envelopes,
    format_age,
    format_timestamp,
    truncate,
    _safe_open_db,
)


# ── Color pairs ──────────────────────────────────────────────────────

C_HEADER = 1
C_HEALTHY = 2
C_DEGRADED = 3
C_OFFLINE = 4
C_ALERT = 5
C_FILTER = 6
C_STATUS = 7
C_ACCENT = 8


def init_colors():
    """Initialize curses color pairs."""
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(C_HEADER, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(C_HEALTHY, curses.COLOR_GREEN, -1)
    curses.init_pair(C_DEGRADED, curses.COLOR_YELLOW, -1)
    curses.init_pair(C_OFFLINE, curses.COLOR_RED, -1)
    curses.init_pair(C_ALERT, curses.COLOR_WHITE, curses.COLOR_RED)
    curses.init_pair(C_FILTER, curses.COLOR_BLACK, curses.COLOR_YELLOW)
    curses.init_pair(C_STATUS, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(C_ACCENT, curses.COLOR_CYAN, -1)


def status_color(status: str) -> int:
    """Return color pair for transport status."""
    return {
        "healthy": curses.color_pair(C_HEALTHY),
        "degraded": curses.color_pair(C_DEGRADED),
        "offline": curses.color_pair(C_OFFLINE),
        "unknown": curses.color_pair(C_OFFLINE),
    }.get(status, 0)


# ── Drawing functions ────────────────────────────────────────────────


def draw_header(stdscr, width, filter_text, filter_mode, sound_enabled):
    """Draw the top header bar."""
    title = " ⚡ Beacon Dashboard v1.1 "
    sound_icon = "🔊" if sound_enabled else "🔇"
    right = f" {sound_icon} [/]filter [e]csv [j]json [s]sound [t]tab [q]uit "

    header = title + " " * max(0, width - len(title) - len(right)) + right
    stdscr.attron(curses.color_pair(C_HEADER))
    stdscr.addnstr(0, 0, header[:width], width)
    stdscr.attroff(curses.color_pair(C_HEADER))

    if filter_mode or filter_text:
        filter_line = f" Filter: {filter_text}{'_' if filter_mode else ''} "
        stdscr.attron(curses.color_pair(C_FILTER))
        stdscr.addnstr(1, 0, filter_line.ljust(width)[:width], width)
        stdscr.attroff(curses.color_pair(C_FILTER))


def draw_transport_health(stdscr, row, width, health_map, selected_transport):
    """Draw transport health panel. Returns number of rows used."""
    stdscr.attron(curses.color_pair(C_ACCENT) | curses.A_BOLD)
    stdscr.addnstr(row, 0, "─── Transport Health ", width)
    stdscr.attroff(curses.color_pair(C_ACCENT) | curses.A_BOLD)
    row += 1

    if not health_map:
        stdscr.addnstr(row, 2, "(no data — waiting for envelopes)", width - 2)
        return 3

    # Column headers
    hdr = f"  {'Transport':<12} {'Status':<10} {'Total':>6} {'Rate/min':>9} {'Last Seen':>10} {'Mayday':>7}"
    stdscr.addnstr(row, 0, hdr[:width], width, curses.A_DIM)
    row += 1

    for name, h in sorted(health_map.items()):
        if row >= curses.LINES - 3:
            break
        marker = "▶ " if name == selected_transport else "  "
        icon = h.status_icon
        col = status_color(h.status)

        line = f"{marker}{name:<12} {icon} {h.status:<7} {h.total:>6} {h.throughput_per_min:>8.1f} {format_age(h.last_seen):>10} {h.mayday_count:>7}"
        stdscr.addnstr(row, 0, line[:width], width, col)
        row += 1

    return row


def draw_top_agents(stdscr, row, width, agents):
    """Draw top agents panel. Returns next row."""
    stdscr.attron(curses.color_pair(C_ACCENT) | curses.A_BOLD)
    stdscr.addnstr(row, 0, "─── Top Agents ", width)
    stdscr.attroff(curses.color_pair(C_ACCENT) | curses.A_BOLD)
    row += 1

    if not agents:
        stdscr.addnstr(row, 2, "(no agents yet)", width - 2)
        return row + 2

    hdr = f"  {'#':>2} {'Agent ID':<20} {'Total':>6} {'Last Seen':>10} {'Kinds'}"
    stdscr.addnstr(row, 0, hdr[:width], width, curses.A_DIM)
    row += 1

    for i, agent in enumerate(agents[:5]):
        if row >= curses.LINES - 3:
            break
        kinds_str = ", ".join(f"{k}:{v}" for k, v in sorted(agent["kinds"].items()))
        line = f"  {i+1:>2} {truncate(agent['agent_id'], 20):<20} {agent['total']:>6} {format_age(agent['last_seen']):>10} {kinds_str}"
        stdscr.addnstr(row, 0, line[:width], width)
        row += 1

    return row + 1


def draw_envelope_list(stdscr, row, width, envelopes, scroll_offset):
    """Draw scrollable envelope list. Returns next row."""
    max_row = curses.LINES - 2
    stdscr.attron(curses.color_pair(C_ACCENT) | curses.A_BOLD)
    stdscr.addnstr(row, 0, f"─── Envelopes ({len(envelopes)} total) ", width)
    stdscr.attroff(curses.color_pair(C_ACCENT) | curses.A_BOLD)
    row += 1

    hdr = f"  {'Time':<10} {'Agent':<16} {'Kind':<12} {'Transport':<12} {'Amount':>8}"
    stdscr.addnstr(row, 0, hdr[:width], width, curses.A_DIM)
    row += 1

    visible = envelopes[scroll_offset:]
    for env in visible:
        if row >= max_row:
            break

        ts = format_timestamp(env.get("received_at"))
        agent = truncate(env.get("agent_id", "?"), 16)
        kind = env.get("kind", "?")
        transport = env.get("transport", "?")
        amount = env.get("amount", 0)
        amount_str = f"{amount:.1f}" if amount > 0 else ""

        # Highlight mayday in red
        attr = 0
        if kind == "mayday":
            attr = curses.color_pair(C_ALERT)

        line = f"  {ts:<10} {agent:<16} {kind:<12} {transport:<12} {amount_str:>8}"
        stdscr.addnstr(row, 0, line[:width], width, attr)
        row += 1

    return row


def draw_status_bar(stdscr, width, message, db_path):
    """Draw bottom status bar."""
    row = curses.LINES - 1
    status = f" {message} | DB: {os.path.basename(db_path)} | {time.strftime('%H:%M:%S UTC', time.gmtime())} "
    stdscr.attron(curses.color_pair(C_STATUS))
    try:
        stdscr.addnstr(row, 0, status.ljust(width)[:width], width)
    except curses.error:
        pass
    stdscr.attroff(curses.color_pair(C_STATUS))


# ── Main loop ────────────────────────────────────────────────────────


def dashboard_main(stdscr, args):
    """Main dashboard loop."""
    init_colors()
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(int(args.refresh * 1000))

    # State
    filter_text = ""
    filter_mode = False
    sound_enabled = not args.no_sound
    scroll_offset = 0
    selected_transport = None
    transport_names = []
    transport_idx = -1
    last_alert_ts = int(time.time())
    status_message = "Ready"
    envelopes = []
    health_map = {}
    top_agents = []

    while True:
        # ── Fetch data ───────────────────────────────────────────
        conn = _safe_open_db(args.db)
        if conn:
            try:
                raw_envelopes = fetch_recent_envelopes(
                    conn,
                    limit=500,
                    kind_filter=None,
                    agent_filter=None,
                    transport_filter=selected_transport,
                )
            except Exception:
                raw_envelopes = []
            finally:
                conn.close()
        else:
            raw_envelopes = []

        # Apply filter
        if filter_text and not filter_mode:
            envelopes = apply_filter(raw_envelopes, filter_text)
        else:
            envelopes = raw_envelopes

        health_map = compute_transport_health(envelopes)
        top_agents = compute_top_agents(envelopes, limit=5)

        # Update transport list
        new_names = sorted(health_map.keys())
        if new_names != transport_names:
            transport_names = new_names

        # Check alerts
        if sound_enabled:
            alerts = check_alerts(raw_envelopes, last_alert_ts)
            if alerts:
                curses.beep()
                status_message = f"⚠ ALERT: {alerts[0]['message']}"
                last_alert_ts = int(time.time())

        # ── Draw ─────────────────────────────────────────────────
        stdscr.erase()
        height, width = stdscr.getmaxyx()

        if height < 10 or width < 40:
            stdscr.addnstr(0, 0, "Terminal too small (min 40x10)", width)
            stdscr.refresh()
            key = stdscr.getch()
            if key == ord("q"):
                break
            continue

        draw_header(stdscr, width, filter_text, filter_mode, sound_enabled)

        row = 3 if (filter_mode or filter_text) else 2
        row = draw_transport_health(stdscr, row, width, health_map, selected_transport)
        row += 1
        row = draw_top_agents(stdscr, row, width, top_agents)
        draw_envelope_list(stdscr, row, width, envelopes, scroll_offset)
        draw_status_bar(stdscr, width, status_message, args.db)

        stdscr.refresh()

        # ── Handle input ─────────────────────────────────────────
        key = stdscr.getch()

        if key == -1:
            continue

        if filter_mode:
            if key == 27:  # Escape
                filter_mode = False
                filter_text = ""
                status_message = "Filter cleared"
            elif key in (10, 13):  # Enter
                filter_mode = False
                status_message = f"Filter: {filter_text}" if filter_text else "Ready"
            elif key in (8, 127, curses.KEY_BACKSPACE):
                filter_text = filter_text[:-1]
            elif 32 <= key <= 126:
                filter_text += chr(key)
            continue

        if key == ord("q"):
            break
        elif key == ord("/"):
            filter_mode = True
            filter_text = ""
            status_message = "Type filter (kind:X agent:X transport:X or free text)"
        elif key == 27:  # Escape
            filter_text = ""
            selected_transport = None
            transport_idx = -1
            scroll_offset = 0
            status_message = "Cleared"
        elif key == ord("e"):
            try:
                filepath = export_csv(envelopes, health_map)
                status_message = f"Exported: {filepath}"
            except Exception as ex:
                status_message = f"Export failed: {ex}"
        elif key == ord("j"):
            try:
                filepath = export_json(envelopes, health_map, top_agents)
                status_message = f"Exported: {filepath}"
            except Exception as ex:
                status_message = f"Export failed: {ex}"
        elif key == ord("s"):
            sound_enabled = not sound_enabled
            status_message = f"Sound: {'ON' if sound_enabled else 'OFF'}"
        elif key == ord("t"):
            if transport_names:
                transport_idx = (transport_idx + 1) % (len(transport_names) + 1)
                if transport_idx == len(transport_names):
                    selected_transport = None
                    status_message = "All transports"
                else:
                    selected_transport = transport_names[transport_idx]
                    status_message = f"Transport: {selected_transport}"
            scroll_offset = 0
        elif key == ord("r"):
            status_message = "Refreshed"
        elif key == curses.KEY_UP:
            scroll_offset = max(0, scroll_offset - 1)
        elif key == curses.KEY_DOWN:
            scroll_offset = min(max(0, len(envelopes) - 1), scroll_offset + 1)
        elif key == curses.KEY_PPAGE:
            scroll_offset = max(0, scroll_offset - 10)
        elif key == curses.KEY_NPAGE:
            scroll_offset = min(max(0, len(envelopes) - 1), scroll_offset + 10)


def main():
    parser = argparse.ArgumentParser(
        description="Beacon Dashboard v1.1 — Live Transport Traffic Monitor"
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB_PATH,
        help=f"Path to rustchain_v2.db (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--refresh",
        type=float,
        default=2.0,
        help="Refresh interval in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--no-sound",
        action="store_true",
        help="Disable sound alerts",
    )

    # Support 'dashboard' subcommand for compatibility with `beacon dashboard`
    args, _ = parser.parse_known_args()
    curses.wrapper(dashboard_main, args)


if __name__ == "__main__":
    main()
