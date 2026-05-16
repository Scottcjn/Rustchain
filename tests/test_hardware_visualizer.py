import importlib.util
from pathlib import Path
from unittest.mock import Mock

import matplotlib
import pytest


matplotlib.use("Agg", force=True)

MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "visualizations" / "visualizer.py"


def load_visualizer_module():
    spec = importlib.util.spec_from_file_location("hardware_visualizer", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_visualize_hardware_fingerprint_closes_radar_line(monkeypatch):
    visualizer = load_visualizer_module()
    visualizer.plt.close("all")
    monkeypatch.setattr(visualizer.plt, "show", Mock())

    visualizer.visualize_hardware_fingerprint(
        {"cpu": 0.8, "memory": 0.6, "disk": 0.4}
    )

    ax = visualizer.plt.gcf().axes[0]
    line = ax.get_lines()[0]

    assert ax.name == "polar"
    assert list(line.get_ydata()) == pytest.approx([0.8, 0.6, 0.4, 0.8])
    assert line.get_xdata()[0] == pytest.approx(line.get_xdata()[-1])
    visualizer.plt.show.assert_called_once()
    visualizer.plt.close("all")


def test_visualize_hardware_fingerprint_sets_labels_and_limits(monkeypatch):
    visualizer = load_visualizer_module()
    visualizer.plt.close("all")
    monkeypatch.setattr(visualizer.plt, "show", Mock())

    visualizer.visualize_hardware_fingerprint({"cpu": 1.0, "gpu": 0.5})

    ax = visualizer.plt.gcf().axes[0]

    assert [tick.get_text() for tick in ax.get_xticklabels()] == ["cpu", "gpu"]
    assert ax.get_ylim() == (0.0, 1.0)
    assert ax.get_title() == "Hardware Fingerprint Visualization"
    visualizer.plt.close("all")
