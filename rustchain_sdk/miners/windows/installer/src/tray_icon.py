"""
RustChain System Tray Icon
Provides a system tray (notification area) icon with controls for the miner.
Uses pystray + Pillow for cross-platform tray icon support on Windows.
"""

import os
import sys
import threading
import subprocess
from pathlib import Path

try:
    import pystray
    from pystray import MenuItem, Menu
    from PIL import Image, ImageDraw, ImageFont
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False


# --- Icon Generation (fallback if .ico not found) ---

def _create_icon_image(color="green", size=64):
    """Generate a simple colored circle icon with 'RC' text."""
    colors = {
        "green": "#4CAF50",
        "gray": "#9E9E9E",
        "red": "#F44336",
        "orange": "#FF9800",
    }
    fill = colors.get(color, colors["gray"])

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw filled circle
    margin = 2
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=fill,
        outline="#222222",
        width=2
    )

    # Draw "RC" text in center
    try:
        font = ImageFont.truetype("arial.ttf", size // 3)
    except (IOError, OSError):
        font = ImageFont.load_default()

    text = "RC"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) // 2
    ty = (size - th) // 2 - 2
    draw.text((tx, ty), text, fill="white", font=font)

    return img


def _load_icon_file():
    """Try to load the .ico file from assets directory."""
    # Check several possible locations
    candidates = [
        Path(__file__).parent.parent / "assets" / "rustchain.ico",
        Path(sys._MEIPASS) / "assets" / "rustchain.ico" if hasattr(sys, "_MEIPASS") else None,
        Path(os.environ.get("APPDATA", "")) / "RustChain" / "rustchain.ico",
    ]
    for p in candidates:
        if p and p.exists():
            try:
                return Image.open(str(p))
            except Exception:
                continue
    return None


class RustChainTray:
    """System tray icon controller for RustChain Miner."""

    def __init__(self, on_start=None, on_stop=None, on_show=None, on_quit=None):
        """
        Args:
            on_start: callback when user clicks "Start Mining"
            on_stop:  callback when user clicks "Stop Mining"
            on_show:  callback when user clicks "Open Dashboard"
            on_quit:  callback when user clicks "Exit"
        """
        if not TRAY_AVAILABLE:
            raise RuntimeError("pystray and Pillow are required for tray icon.")

        self.on_start = on_start
        self.on_stop = on_stop
        self.on_show = on_show
        self.on_quit = on_quit

        self._mining = False
        self._status_text = "Idle"

        # Load or generate icon
        self._icon_active = _load_icon_file() or _create_icon_image("green")
        self._icon_idle = _create_icon_image("gray")
        self._icon_error = _create_icon_image("red")

        self.icon = pystray.Icon(
            name="RustChainMiner",
            icon=self._icon_idle,
            title="RustChain Miner — Idle",
            menu=self._build_menu()
        )

    def _build_menu(self):
        """Build the right-click context menu."""
        return Menu(
            MenuItem(
                "Start Mining",
                self._on_start_click,
                visible=lambda item: not self._mining
            ),
            MenuItem(
                "Stop Mining",
                self._on_stop_click,
                visible=lambda item: self._mining
            ),
            Menu.SEPARATOR,
            MenuItem("Open Dashboard", self._on_show_click),
            MenuItem("View Logs", self._on_open_logs),
            Menu.SEPARATOR,
            MenuItem(
                lambda text: f"Status: {self._status_text}",
                None,
                enabled=False
            ),
            Menu.SEPARATOR,
            MenuItem("Exit", self._on_quit_click),
        )

    # --- Menu action handlers ---

    def _on_start_click(self, icon, item):
        self._mining = True
        self.set_status("Mining...", "active")
        if self.on_start:
            self.on_start()

    def _on_stop_click(self, icon, item):
        self._mining = False
        self.set_status("Idle", "idle")
        if self.on_stop:
            self.on_stop()

    def _on_show_click(self, icon, item):
        if self.on_show:
            self.on_show()

    def _on_open_logs(self, icon, item):
        log_dir = Path(os.environ.get("APPDATA", Path.home())) / "RustChain" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(log_dir))
        except Exception:
            subprocess.Popen(["explorer", str(log_dir)])

    def _on_quit_click(self, icon, item):
        self._mining = False
        if self.on_quit:
            self.on_quit()
        icon.stop()

    # --- Public API ---

    def set_status(self, text, state="idle"):
        """
        Update tray icon status.
        state: 'active', 'idle', 'error'
        """
        self._status_text = text

        if state == "active":
            self.icon.icon = self._icon_active
            self._mining = True
        elif state == "error":
            self.icon.icon = self._icon_error
        else:
            self.icon.icon = self._icon_idle

        self.icon.title = f"RustChain Miner — {text}"
        # Force menu rebuild to reflect state changes
        self.icon.menu = self._build_menu()

    def run(self):
        """Run the tray icon (blocks the calling thread)."""
        self.icon.run()

    def run_detached(self):
        """Run the tray icon in a background thread."""
        t = threading.Thread(target=self.icon.run, daemon=True)
        t.start()
        return t

    def stop(self):
        """Stop the tray icon."""
        self.icon.stop()


if __name__ == "__main__":
    # Quick standalone test
    def on_start():
        print("[Tray] Start Mining clicked")

    def on_stop():
        print("[Tray] Stop Mining clicked")

    def on_show():
        print("[Tray] Open Dashboard clicked")

    def on_quit():
        print("[Tray] Exit clicked")

    tray = RustChainTray(
        on_start=on_start,
        on_stop=on_stop,
        on_show=on_show,
        on_quit=on_quit
    )
    print("Tray icon running... Right-click the tray icon to test.")
    tray.run()
