"""Native keyboard-accessible preferences, applied as one transaction."""
import copy
from pathlib import Path
from gi.repository import Gdk, Gtk

from .. import autostart
from ..config import validate


class SettingsDialog(Gtk.Dialog):
    def __init__(self, app):
        super().__init__(title="Mint Meter Settings", transient_for=app.window, modal=False)
        self.app = app
        self.set_application(app)
        self.set_default_size(460, 560)
        self.set_border_width(12)
        self.add_buttons("_Close", Gtk.ResponseType.CLOSE, "_Apply", Gtk.ResponseType.APPLY)
        self.connect("response", self.respond)
        self.connect("key-press-event", self.key_press)
        self.grid = Gtk.Grid(column_spacing=18, row_spacing=12, margin=8)
        self.get_content_area().add(self.grid)
        self.row = 0
        c = app.config
        self.theme = self.combo("T_heme", [("dark", "Dark"), ("light", "Light")], c["appearance"]["theme"])
        self.opacity = self.spin("Background _opacity", c["appearance"]["background_opacity"], .35, 1, .05, 2)
        self.scale = self.spin("Widget _scale", c["appearance"]["scale"], .75, 2, .25, 2)
        self.units = self.combo("_Units", [("decimal", "Decimal · GB, MB/s"), ("binary", "Binary · GiB, MiB/s")], c["appearance"]["units"])
        self.accent = Gtk.ColorButton()
        rgba = Gdk.RGBA()
        rgba.parse(c["appearance"]["accent_color"])
        self.accent.set_rgba(rgba)
        self.add_row("Accent colo_r", self.accent)
        self.interval = self.combo("Refresh _interval", [(str(v), f"{v:g} seconds") for v in (.5, 1., 2., 5.)], str(float(c["sampling"]["interval_seconds"])))
        names = app.window.sample.interfaces if app.window.sample else ()
        selected = c["network"]["interface"]
        names = sorted(set(names) | ({selected} if selected != "auto" else set()))
        self.interface = self.combo("Network inter_face", [("auto", "Automatic · routed interface")] + [(v, v) for v in names], selected)
        self.path = Gtk.Entry(text=c["disk"]["path"])
        self.path.set_tooltip_text("Measures the containing filesystem, not disk read/write speed. Missing paths show Unavailable.")
        self.add_row("_Disk path", self.path)
        hint = Gtk.Label(label="Disk: capacity of the filesystem containing this path.", xalign=0)
        hint.get_style_context().add_class("dim-label")
        self.grid.attach(hint, 0, self.row, 2, 1)
        self.row += 1
        self.locked = self.check("_Lock position", c["window"]["locked"])
        self.above = self.check("Always on _top", c["window"]["always_on_top"])
        self.workspaces = self.check("Show on all _workspaces", c["window"]["all_workspaces"])
        self.startup = self.check("Start at lo_gin", autostart.enabled())
        if not Path("/usr/bin/mint-meter").is_file():
            self.startup.set_sensitive(False)
            self.startup.set_tooltip_text("Install the .deb to enable a stable login startup command.")
        self.status = Gtk.Label(xalign=0, wrap=True)
        self.status.set_max_width_chars(48)
        self.grid.attach(self.status, 0, self.row, 2, 1)
        if app.store.notice:
            self.status.set_text(app.store.notice)
        self.show_all()

    def add_row(self, label, widget):
        title = Gtk.Label.new_with_mnemonic(label)
        title.set_xalign(0)
        title.set_mnemonic_widget(widget)
        widget.get_accessible().set_name(label.replace("_", ""))
        widget.set_hexpand(True)
        self.grid.attach(title, 0, self.row, 1, 1)
        self.grid.attach(widget, 1, self.row, 1, 1)
        self.row += 1

    def combo(self, title, choices, selected):
        widget = Gtk.ComboBoxText()
        for key, label in choices:
            widget.append(key, label)
        widget.set_active_id(selected)
        self.add_row(title, widget)
        return widget

    def spin(self, title, value, low, high, step, digits):
        widget = Gtk.SpinButton.new_with_range(low, high, step)
        widget.set_digits(digits)
        widget.set_value(value)
        self.add_row(title, widget)
        return widget

    def check(self, title, value):
        widget = Gtk.CheckButton.new_with_mnemonic(title)
        widget.set_active(value)
        self.grid.attach(widget, 0, self.row, 2, 1)
        self.row += 1
        return widget

    def key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
            return True
        return False

    def respond(self, dialog, response):
        if response != Gtk.ResponseType.APPLY:
            self.destroy()
            return
        config = copy.deepcopy(self.app.config)
        path = self.path.get_text().strip()
        if not Path(path).is_absolute() or not Path(path).exists():
            self.status.set_text("Choose an existing absolute path. Its containing filesystem will be measured.")
            return
        a = config["appearance"]
        a.update(theme=self.theme.get_active_id(), background_opacity=self.opacity.get_value(),
                 scale=self.scale.get_value(), units=self.units.get_active_id())
        rgba = self.accent.get_rgba()
        a["accent_color"] = "#{:02X}{:02X}{:02X}".format(*(round(v * 255) for v in (rgba.red, rgba.green, rgba.blue)))
        config["sampling"]["interval_seconds"] = float(self.interval.get_active_id())
        config["network"]["interface"] = self.interface.get_active_id()
        config["disk"]["path"] = path
        config["window"].update(locked=self.locked.get_active(), always_on_top=self.above.get_active(),
                                 all_workspaces=self.workspaces.get_active())
        try:
            if self.startup.get_active() != autostart.enabled():
                autostart.set_enabled(self.startup.get_active())
            self.app.apply_config(validate(config))
        except (OSError, ValueError) as error:
            self.status.set_text(f"Could not save preferences: {error}")
            return
        self.status.set_text("Preferences applied.")
        self.present()
