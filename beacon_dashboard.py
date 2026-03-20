// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import curses
import sqlite3
import json
import csv
import time
import threading
import subprocess
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional, Any

DB_PATH = os.environ.get('RUSTCHAIN_DB', 'beacon.db')
SOUND_ENABLED = os.environ.get('BEACON_SOUND', '0') == '1'

class BeaconDashboard:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.running = True
        self.filter_text = ""
        self.selected_transport = None
        self.last_update = time.time()
        self.export_status = ""
        self.alert_queue = []

        curses.curs_set(0)
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_RED, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_CYAN, -1)
        curses.init_pair(5, curses.COLOR_MAGENTA, -1)

        self.setup_db()
        self.start_data_thread()

    def setup_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS beacon_transports (
                id INTEGER PRIMARY KEY,
                transport_id TEXT UNIQUE,
                status TEXT,
                last_seen TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                agent_id TEXT
            )''')

            conn.execute('''CREATE TABLE IF NOT EXISTS beacon_messages (
                id INTEGER PRIMARY KEY,
                transport_id TEXT,
                agent_id TEXT,
                message_type TEXT,
                content TEXT,
                priority INTEGER DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            conn.execute('''CREATE TABLE IF NOT EXISTS beacon_alerts (
                id INTEGER PRIMARY KEY,
                alert_type TEXT,
                transport_id TEXT,
                agent_id TEXT,
                message TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

    def start_data_thread(self):
        self.data_thread = threading.Thread(target=self.data_collector, daemon=True)
        self.data_thread.start()

    def data_collector(self):
        while self.running:
            try:
                self.update_transport_data()
                self.check_for_alerts()
                time.sleep(2)
            except Exception:
                pass

    def update_transport_data(self):
        current_time = datetime.now()

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''INSERT OR REPLACE INTO beacon_transports
                           (transport_id, status, last_seen, agent_id)
                           VALUES (?, ?, ?, ?)''',
                         (f"transport_{int(time.time()) % 1000}",
                          "ACTIVE" if time.time() % 10 > 3 else "DEGRADED",
                          current_time, f"agent_{int(time.time()) % 50}"))

    def check_for_alerts(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''SELECT * FROM beacon_messages
                                   WHERE message_type IN ('mayday', 'high_value_tip')
                                   AND timestamp > datetime('now', '-30 seconds')''')

            for row in cursor:
                alert = {
                    'type': row[3],
                    'transport': row[1],
                    'agent': row[2],
                    'message': row[4],
                    'timestamp': row[6]
                }
                self.alert_queue.append(alert)

                if SOUND_ENABLED:
                    self.play_alert_sound(row[3])

    def play_alert_sound(self, alert_type):
        try:
            if alert_type == 'mayday':
                subprocess.run(['play', '-q', '/usr/share/sounds/alsa/Front_Right.wav'],
                             check=False, capture_output=True)
            elif alert_type == 'high_value_tip':
                subprocess.run(['play', '-q', '/usr/share/sounds/alsa/Front_Left.wav'],
                             check=False, capture_output=True)
        except (FileNotFoundError, subprocess.SubprocessError):
            pass

    def get_transport_health(self) -> Dict[str, Any]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''SELECT status, COUNT(*) as count
                                   FROM beacon_transports
                                   WHERE last_seen > datetime('now', '-5 minutes')
                                   GROUP BY status''')

            health_data = {'ACTIVE': 0, 'DEGRADED': 0, 'OFFLINE': 0}
            for status, count in cursor:
                health_data[status] = count

            total_transports = sum(health_data.values())

            cursor = conn.execute('''SELECT COUNT(*) FROM beacon_messages
                                   WHERE timestamp > datetime('now', '-1 hour')''')
            msg_count = cursor.fetchone()[0]

            return {
                'total_transports': total_transports,
                'status_counts': health_data,
                'hourly_messages': msg_count,
                'health_percentage': (health_data['ACTIVE'] / max(total_transports, 1)) * 100
            }

    def get_transport_stats(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''SELECT transport_id, status, message_count,
                                          agent_id, last_seen
                                   FROM beacon_transports
                                   ORDER BY message_count DESC LIMIT 20''')

            stats = []
            for row in cursor:
                if not self.filter_text or self.filter_text.lower() in str(row).lower():
                    stats.append({
                        'transport_id': row[0],
                        'status': row[1],
                        'message_count': row[2],
                        'agent_id': row[3],
                        'last_seen': row[4]
                    })

            return stats

    def get_top_agents(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''SELECT agent_id, COUNT(*) as message_count,
                                          MAX(timestamp) as last_activity
                                   FROM beacon_messages
                                   WHERE timestamp > datetime('now', '-24 hours')
                                   GROUP BY agent_id
                                   ORDER BY message_count DESC LIMIT 10''')

            agents = []
            for row in cursor:
                agents.append({
                    'agent_id': row[0],
                    'message_count': row[1],
                    'last_activity': row[2]
                })

            return agents

    def export_data(self, format_type: str, filename: str) -> bool:
        try:
            health = self.get_transport_health()
            transports = self.get_transport_stats()
            agents = self.get_top_agents()

            export_data = {
                'timestamp': datetime.now().isoformat(),
                'health': health,
                'transports': transports,
                'top_agents': agents,
                'filter_applied': self.filter_text
            }

            if format_type.lower() == 'json':
                with open(filename, 'w') as f:
                    json.dump(export_data, f, indent=2)
            elif format_type.lower() == 'csv':
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)

                    writer.writerow(['# Health Summary'])
                    writer.writerow(['Total Transports', health['total_transports']])
                    writer.writerow(['Health %', f"{health['health_percentage']:.1f}"])
                    writer.writerow(['Hourly Messages', health['hourly_messages']])
                    writer.writerow([])

                    writer.writerow(['# Transport Stats'])
                    writer.writerow(['Transport ID', 'Status', 'Messages', 'Agent', 'Last Seen'])
                    for t in transports:
                        writer.writerow([t['transport_id'], t['status'],
                                       t['message_count'], t['agent_id'], t['last_seen']])

                    writer.writerow([])
                    writer.writerow(['# Top Agents'])
                    writer.writerow(['Agent ID', 'Messages', 'Last Activity'])
                    for a in agents:
                        writer.writerow([a['agent_id'], a['message_count'], a['last_activity']])

            return True
        except Exception:
            return False

    def draw_header(self, y: int) -> int:
        header = "🔥 BEACON DASHBOARD v1.1 🔥"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.stdscr.addstr(y, 2, header, curses.A_BOLD | curses.color_pair(4))
        self.stdscr.addstr(y, 50, f"Last Update: {timestamp}")

        if self.export_status:
            self.stdscr.addstr(y + 1, 2, f"Export: {self.export_status}", curses.color_pair(3))

        return y + 2

    def draw_health_panel(self, y: int) -> int:
        health = self.get_transport_health()

        self.stdscr.addstr(y, 2, "═══ TRANSPORT HEALTH ═══", curses.A_BOLD)
        y += 1

        total = health['total_transports']
        active = health['status_counts']['ACTIVE']
        degraded = health['status_counts']['DEGRADED']
        offline = health['status_counts']['OFFLINE']

        health_pct = health['health_percentage']
        health_color = curses.color_pair(1) if health_pct > 80 else \
                      curses.color_pair(3) if health_pct > 50 else curses.color_pair(2)

        self.stdscr.addstr(y, 4, f"Total Transports: {total}")
        self.stdscr.addstr(y, 30, f"Health: {health_pct:.1f}%", health_color)
        y += 1

        self.stdscr.addstr(y, 4, f"Active: {active}", curses.color_pair(1))
        self.stdscr.addstr(y, 18, f"Degraded: {degraded}", curses.color_pair(3))
        self.stdscr.addstr(y, 35, f"Offline: {offline}", curses.color_pair(2))
        y += 1

        self.stdscr.addstr(y, 4, f"Hourly Messages: {health['hourly_messages']}")

        return y + 2

    def draw_transport_stats(self, y: int) -> int:
        start_y = y
        max_height = 15

        self.stdscr.addstr(y, 2, "═══ TRANSPORT STATS ═══", curses.A_BOLD)
        y += 1

        if self.filter_text:
            self.stdscr.addstr(y, 4, f"Filter: '{self.filter_text}'", curses.color_pair(5))
            y += 1

        headers = f"{'Transport ID':<15} {'Status':<10} {'Msgs':<6} {'Agent':<12} {'Last Seen':<19}"
        self.stdscr.addstr(y, 4, headers, curses.A_UNDERLINE)
        y += 1

        transports = self.get_transport_stats()
        displayed = 0

        for transport in transports:
            if displayed >= max_height - 4:
                break

            status_color = curses.color_pair(1) if transport['status'] == 'ACTIVE' else \
                          curses.color_pair(3) if transport['status'] == 'DEGRADED' else \
                          curses.color_pair(2)

            line = f"{transport['transport_id']:<15} {transport['status']:<10} " \
                  f"{transport['message_count']:<6} {transport['agent_id']:<12} " \
                  f"{transport['last_seen'][:19]:<19}"

            if transport['transport_id'] == self.selected_transport:
                self.stdscr.addstr(y, 4, line, curses.A_REVERSE | status_color)
            else:
                self.stdscr.addstr(y, 4, line, status_color)

            y += 1
            displayed += 1

        return max(y, start_y + max_height)

    def draw_top_agents(self, y: int) -> int:
        self.stdscr.addstr(y, 2, "═══ TOP AGENTS (24h) ═══", curses.A_BOLD)
        y += 1

        headers = f"{'Agent ID':<15} {'Messages':<10} {'Last Activity':<19}"
        self.stdscr.addstr(y, 4, headers, curses.A_UNDERLINE)
        y += 1

        agents = self.get_top_agents()

        for agent in agents[:8]:
            line = f"{agent['agent_id']:<15} {agent['message_count']:<10} " \
                  f"{agent['last_activity'][:19]:<19}"
            self.stdscr.addstr(y, 4, line)
            y += 1

        return y + 1

    def draw_alerts(self, y: int) -> int:
        if not self.alert_queue:
            return y

        self.stdscr.addstr(y, 2, "═══ RECENT ALERTS ═══", curses.A_BOLD | curses.color_pair(2))
        y += 1

        recent_alerts = self.alert_queue[-5:]
        for alert in recent_alerts:
            alert_color = curses.color_pair(2) if alert['type'] == 'mayday' else curses.color_pair(3)

            alert_text = f"[{alert['type'].upper()}] {alert['transport']} | {alert['message'][:30]}"
            self.stdscr.addstr(y, 4, alert_text, alert_color | curses.A_BOLD)
            y += 1

        return y + 1

    def draw_controls(self, y: int) -> int:
        controls = [
            "Controls: [f]ilter  [e]xport  [c]lear alerts  [q]uit  [r]efresh",
            "Export: [j]son | [v]csv    Filter: type text, [ESC] to clear"
        ]

        for i, control in enumerate(controls):
            self.stdscr.addstr(y + i, 2, control, curses.color_pair(4))

        return y + len(controls)

    def handle_filter_input(self):
        curses.echo()
        curses.curs_set(1)

        height, width = self.stdscr.getmaxyx()
        prompt_y = height - 3

        self.stdscr.addstr(prompt_y, 2, "Filter: ")
        self.stdscr.clrtoeol()

        try:
            filter_input = self.stdscr.getstr(prompt_y, 10, 40).decode('utf-8')
            self.filter_text = filter_input
        except (KeyboardInterrupt, UnicodeDecodeError):
            pass

        curses.noecho()
        curses.curs_set(0)

    def handle_export(self, format_type: str):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"beacon_export_{timestamp}.{format_type}"

        if self.export_data(format_type, filename):
            self.export_status = f"Exported to {filename}"
        else:
            self.export_status = "Export failed"

    def run(self):
        while self.running:
            try:
                self.stdscr.clear()

                y = 1
                y = self.draw_header(y)
                y = self.draw_health_panel(y)
                y = self.draw_transport_stats(y)

                height, width = self.stdscr.getmaxyx()
                remaining_height = height - y - 6

                if remaining_height > 5:
                    y = self.draw_top_agents(y)

                y = self.draw_alerts(y)
                y = self.draw_controls(height - 4)

                self.stdscr.refresh()

                self.stdscr.timeout(1000)
                key = self.stdscr.getch()

                if key == ord('q'):
                    break
                elif key == ord('f'):
                    self.handle_filter_input()
                elif key == ord('j'):
                    self.handle_export('json')
                elif key == ord('v'):
                    self.handle_export('csv')
                elif key == ord('c'):
                    self.alert_queue.clear()
                    self.export_status = ""
                elif key == ord('r'):
                    self.last_update = time.time()
                elif key == 27:  # ESC
                    self.filter_text = ""
                    self.export_status = ""

            except KeyboardInterrupt:
                break
            except curses.error:
                pass

        self.running = False

def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'dashboard':
        try:
            curses.wrapper(lambda stdscr: BeaconDashboard(stdscr).run())
        except Exception as e:
            print(f"Dashboard error: {e}")
            return 1
    else:
        print("Usage: python beacon_dashboard.py dashboard")
        return 1

    return 0

if __name__ == '__main__':
    exit(main())
