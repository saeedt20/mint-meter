"""Application lifecycle and D-Bus single-instance command forwarding."""
import argparse
import queue
import signal
import sys

from . import __version__


def parser():
    result = argparse.ArgumentParser(prog="mint-meter", description="A compact desktop system monitor")
    group = result.add_mutually_exclusive_group()
    group.add_argument("--settings", action="store_true", help="open preferences")
    group.add_argument("--reset-position", action="store_true", help="restore the upper-right position")
    group.add_argument("--quit", action="store_true", help="quit the running instance")
    result.add_argument("--version", action="version", version=f"Mint Meter {__version__}")
    return result


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    parser().parse_args(args)  # Help/version work without GTK or a display.
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        gi.require_version("PangoCairo", "1.0")
        from gi.repository import Gdk, Gio, GLib, Gtk
        from .config import ConfigStore, validate
        from .metrics import Collector
        from .ui.settings import SettingsDialog
        from .ui.widget import MeterWindow
    except (ImportError, ValueError) as error:
        print(f"Mint Meter requires the system GTK 3 / Cairo / psutil packages: {error}", file=sys.stderr)
        return 1
    if Gdk.Display.get_default() is None:
        print("Mint Meter needs a graphical session (X11 recommended).", file=sys.stderr)
        return 1
    Gtk.Window.set_default_icon_name("mint-meter")

    class Application(Gtk.Application):
        def __init__(self):
            super().__init__(application_id="org.mintmeter.Widget", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
            self.window = self.settings = self.collector = None
            self.poll_id = 0
            self.store = ConfigStore()
            self.config = None

        def do_command_line(self, command_line):
            options = parser().parse_args(command_line.get_arguments()[1:])
            if options.quit:
                self.quit()
                return 0
            existing = self.window is not None
            if not existing:
                try:
                    self.config = self.store.load()
                except OSError as error:
                    print(f"Cannot read preferences: {error}", file=sys.stderr)
                    return 1
                self.window = MeterWindow(self)
                self.collector = Collector(self.config)
                self.collector.start()
                self.poll_id = GLib.timeout_add(200, self.poll)
                if "Wayland" in type(Gdk.Display.get_default()).__name__:
                    print("Wayland: positioning, stacking, and workspace hints may not be supported.", file=sys.stderr)
            if options.reset_position:
                self.reset_position()
            elif options.settings or existing:
                self.open_settings()
            return 0

        def poll(self):
            try:
                sample = self.collector.results.get_nowait()
                if sample.generation == self.collector.generation:
                    self.window.update(sample)
            except queue.Empty:
                pass
            return True

        def save(self):
            try:
                self.store.save(self.config)
            except OSError as error:
                self.store.notice = f"Preferences could not be saved: {error}"
                if self.settings:
                    self.settings.status.set_text(self.store.notice)

        def apply_config(self, config):
            checked = validate(config)
            self.store.save(checked)
            sampling_changed = any(self.config[k] != checked[k] for k in ("sampling", "network", "disk"))
            self.config = checked
            self.window.apply()
            if sampling_changed:
                self.collector.configure(self.config)

        def reset_position(self):
            self.config["window"].update(position=None, monitor="primary")
            self.window.reposition()
            self.save()

        def open_settings(self):
            if self.settings is None:
                self.settings = SettingsDialog(self)
                self.settings.connect("destroy", self.settings_closed)
            self.settings.present()

        def settings_closed(self, *_):
            self.settings = None

        def do_shutdown(self):
            if self.poll_id:
                GLib.source_remove(self.poll_id)
            if self.collector:
                self.collector.stop()
            if self.window:
                if self.window.dragging or self.window.position_timer:
                    self.window.cleanup()
                    self.window.save_position()
                self.window.destroy()
            Gtk.Application.do_shutdown(self)

    app = Application()
    for sig in (signal.SIGINT, signal.SIGTERM):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: app.quit() or False)
    return app.run(["mint-meter"] + list(args))
