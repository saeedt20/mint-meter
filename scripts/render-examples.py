#!/usr/bin/python3
"""Capture the real GTK interface with explicit, deterministic example data.

Run only on an isolated Xvfb display with temporary XDG directories. No metric
collector is started. These documentation previews are not live measurements.
"""
import math
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import cairo
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gio, GLib, Gtk
from tallydesklet.config import validate
from tallydesklet.metrics import Capacity, Sample
from tallydesklet.network import Rate
from tallydesklet.usage import UsageTotals
from tallydesklet.ui.settings import SettingsDialog
from tallydesklet.ui.widget import MeterWindow


def settle():
    context = GLib.MainContext.default()
    until = time.monotonic() + .4
    while time.monotonic() < until:
        while context.pending():
            context.iteration(False)
        time.sleep(.01)


def capture(widget, path):
    settle()
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                 widget.get_allocated_width(), widget.get_allocated_height())
    widget.draw(cairo.Context(surface))
    surface.write_to_png(str(path))
    print(f"Example-data GTK preview: {path.name}")


def main():
    output = ROOT / "docs/examples"
    output.mkdir(parents=True, exist_ok=True)
    # A fixed standard theme avoids exposing the user's desktop appearance.
    Gtk.Settings.get_default().set_property("gtk-theme-name", "Adwaita")
    Gtk.Settings.get_default().set_property("gtk-font-name", "Sans 10")
    app = Gtk.Application(application_id="org.tallydesklet.Examples",
                          flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.register(None)
    app.store = SimpleNamespace(notice=None)
    app.save = lambda: None
    app.apply_config = lambda config: None
    for theme in ("dark", "light"):
        app.config = validate({"appearance": {"theme": theme, "scale": 2.0}})
        app.window = MeterWindow(app)
        for second in range(61):
            cpu = 24 + 9 * math.sin(second * .23) + 4 * math.cos(second * .61)
            down = 3_800_000 + 1_000_000 * math.sin(second * .17)
            up = 420_000 + 160_000 * math.cos(second * .31)
            if second == 60:
                cpu, down, up = 24, 3_800_000, 420_000
            app.window.update(Sample(float(second), cpu,
                Capacity(6_200_000_000, 16_000_000_000, 9_800_000_000),
                Capacity(128_000_000_000, 512_000_000_000, 384_000_000_000),
                Rate("example0", down, up, "Ready"), ("example0",), 0,
                UsageTotals(420_000_000, 2_800_000_000, "2026-01-04")))
        capture(app.window, output / f"{theme}.png")
        if theme == "dark":
            settings = SettingsDialog(app)
            capture(settings, output / "settings.png")
            settings.destroy()
        app.window.destroy()
        settle()


if __name__ == "__main__":
    main()
