"""Compact Cairo card with native GTK interaction and desktop hints."""
import time
import cairo
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo

from ..formatting import capacity, quantity
from ..history import GraphScale, History
from ..position import place
from .graphs import bar, graph
from .theme import CYAN, HEIGHT, RADIUS, THEMES, WIDTH, color, rounded


class MeterWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Mint Meter")
        self.app = app
        self.sample = None
        self.cpu, self.down, self.up = History(), History(), History()
        self.net_scale = GraphScale()
        self.position_timer = 0
        self.dragging = False
        self.drag_origin = None
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_accept_focus(False)
        self.set_focus_on_map(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_app_paintable(True)
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.get_style_context().add_class("mint-meter")
        css = Gtk.CssProvider()
        css.load_from_data(b"window.mint-meter { background: transparent; } "
                           b".mint-gear { background: transparent; border: none; box-shadow: none; padding: 0; min-width: 24px; min-height: 24px; }")
        Gtk.StyleContext.add_provider_for_screen(screen, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.fixed = Gtk.Fixed()
        self.add(self.fixed)
        self.canvas = Gtk.DrawingArea()
        self.canvas.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
                               Gdk.EventMask.POINTER_MOTION_MASK)
        self.canvas.connect("draw", self.draw_card)
        self.canvas.connect("button-press-event", self.button_press)
        self.canvas.connect("motion-notify-event", self.drag_motion)
        self.canvas.connect("button-release-event", self.drag_end)
        self.canvas.set_has_tooltip(True)
        self.canvas.connect("query-tooltip", self.tooltip)
        self.canvas.get_accessible().set_name("System metrics")
        self.fixed.put(self.canvas, 0, 0)
        self.gear = Gtk.Button()
        self.gear.set_image(Gtk.Image.new_from_icon_name("emblem-system-symbolic", Gtk.IconSize.MENU))
        self.gear.get_style_context().add_class("mint-gear")
        self.gear.set_tooltip_text("Mint Meter menu")
        self.gear.get_accessible().set_name("Mint Meter settings and actions")
        self.gear.connect("clicked", lambda button: self.show_menu())
        self.fixed.put(self.gear, 280, 12)
        self.connect("delete-event", lambda *_: app.quit() or True)
        screen.connect("monitors-changed", lambda *_: self.reposition())
        screen.connect("size-changed", lambda *_: self.reposition())
        screen.connect("composited-changed", lambda *_: self.queue_draw())
        self.connect("destroy", self.cleanup)
        self.apply()
        self.show_all()
        GLib.idle_add(self.reposition)

    @property
    def config(self):
        return self.app.config

    def apply(self):
        scale = self.config["appearance"]["scale"]
        w, h = round(WIDTH * scale), round(HEIGHT * scale)
        self.canvas.set_size_request(w, h)
        self.fixed.set_size_request(w, h)
        self.fixed.move(self.gear, round(278 * scale), round(11 * scale))
        self.gear.set_size_request(round(26*scale), round(26*scale))
        self.gear.get_image().set_pixel_size(round(16*scale))
        self.resize(w, h)
        settings = self.config["window"]
        above = settings["always_on_top"]
        # Managed DESKTOP windows survive Show Desktop without reserving a strut.
        self.set_keep_above(False)
        self.set_keep_below(False)
        self.set_type_hint(Gdk.WindowTypeHint.NORMAL if above else Gdk.WindowTypeHint.DESKTOP)
        self.set_keep_above(above)
        self.set_keep_below(not above)
        self.stick() if settings["all_workspaces"] else self.unstick()
        self.gear.get_style_context().add_class("mint-gear")
        fg = Gdk.RGBA()
        fg.parse(THEMES[self.config["appearance"]["theme"]]["muted"])
        self.gear.override_color(Gtk.StateFlags.NORMAL, fg)
        self.reposition()
        self.queue_draw()

    def monitor_key(self, monitor):
        display = self.get_display()
        screen = self.get_screen()
        for i in range(display.get_n_monitors()):
            if display.get_monitor(i) == monitor:
                return screen.get_monitor_plug_name(i) or f"monitor-{i}"
        return "primary"

    def reposition(self):
        display = self.get_display()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        for i in range(display.get_n_monitors()):
            candidate = display.get_monitor(i)
            if self.monitor_key(candidate) == self.config["window"]["monitor"]:
                monitor = candidate
                break
        if monitor is None:
            return False
        area = monitor.get_workarea()
        scale = self.config["appearance"]["scale"]
        position = place((area.x, area.y, area.width, area.height),
                         (round(WIDTH * scale), round(HEIGHT * scale)),
                         self.config["window"]["position"], self.config["window"]["margin"])
        self.move(*position)
        return False

    def save_position(self):
        self.position_timer = 0
        self.dragging = False
        self.config["window"]["position"] = list(self.get_position())
        monitor = self.get_display().get_monitor_at_window(self.get_window())
        self.config["window"]["monitor"] = self.monitor_key(monitor)
        self.app.save()
        return False

    def cleanup(self, *_):
        if self.position_timer:
            GLib.source_remove(self.position_timer)
            self.position_timer = 0

    def button_press(self, widget, event):
        if event.button == 3:
            self.show_menu(event)
            return True
        if event.button == 1 and event.y < 44*self.config["appearance"]["scale"] and not self.config["window"]["locked"]:
            self.dragging = True
            self.drag_origin = (event.x_root, event.y_root, *self.get_position())
            # Xfwm refuses _NET_WM_MOVERESIZE for DESKTOP windows. Keep this a
            # managed window and move on pointer motion instead of changing type.
            self.canvas.grab_add()
            return True
        return False

    def drag_motion(self, widget, event):
        if self.dragging and self.drag_origin:
            rx, ry, x, y = self.drag_origin
            self.move(round(x + event.x_root-rx), round(y + event.y_root-ry))
            return True
        return False

    def drag_end(self, widget, event):
        if self.dragging and event.button == 1:
            self.canvas.grab_remove()
            self.drag_origin = None
            self.dragging = False
            # Let the final ConfigureNotify arrive before reading/saving position.
            self.position_timer = GLib.timeout_add(150, self.save_position)
            return True
        return False

    def show_menu(self, event=None):
        menu = Gtk.Menu()
        settings = Gtk.MenuItem(label="Settings…")
        settings.connect("activate", lambda *_: self.app.open_settings())
        menu.append(settings)
        for key, label in (("locked", "Lock position"), ("always_on_top", "Always on top")):
            item = Gtk.CheckMenuItem(label=label)
            item.set_active(self.config["window"][key])
            item.connect("toggled", self.toggle, key)
            menu.append(item)
        for label, action in (("Reset position", self.app.reset_position), ("Quit", self.app.quit)):
            item = Gtk.MenuItem(label=label)
            item.connect("activate", lambda _, fn=action: fn())
            menu.append(item)
        menu.show_all()
        self.menu = menu
        if event:
            menu.popup_at_pointer(event)
        else:
            menu.popup_at_widget(self.gear, Gdk.Gravity.SOUTH_EAST, Gdk.Gravity.NORTH_EAST, None)

    def toggle(self, item, key):
        self.config["window"][key] = item.get_active()
        self.app.apply_config(self.config)

    def update(self, sample):
        previous = self.sample
        if previous and previous.network.interface != sample.network.interface:
            self.down.points.clear()
            self.up.points.clear()
        self.sample = sample
        self.cpu.append(sample.time, sample.cpu)
        self.down.append(sample.time, sample.network.down)
        self.up.append(sample.time, sample.network.up)
        peak = max([v for history in (self.down, self.up) for _, v in history.points if v is not None] or [0])
        self.net_scale.update(peak, sample.time-previous.time if previous else 1)
        self.canvas.get_accessible().set_description(self.summary())
        self.canvas.queue_draw()

    def summary(self):
        if not self.sample:
            return "Waiting for the first system sample"
        s = self.sample
        binary = self.config["appearance"]["units"] == "binary"
        lines = [f"CPU: {s.cpu:g}%" if s.cpu is not None else "CPU: warming up / unavailable"]
        for name, metric in (("RAM", s.ram), ("System disk", s.disk)):
            lines.append(f"{name}: {capacity(metric.used, metric.total, binary)}; {metric.fraction:.1%} used; "
                         f"{quantity(metric.available, binary)} available" if metric else f"{name}: Unavailable")
        lines += [f"Filesystem containing: {self.config['disk']['path']}",
                  f"Weekly usage: {quantity(s.usage.weekly, binary)}; daily usage: {quantity(s.usage.daily, binary)}",
                  "Usage combines download + upload on the selected interface while Mint Meter runs.",
                  "Daily reset: local midnight. Weekly reset: Sunday, local midnight.",
                  "Unobserved traffic during closure, reconnects or gaps over 15 seconds is excluded.",
                  f"Interface: {s.network.interface or self.config['network']['interface']} · {s.network.status}",
                  f"Download: {quantity(s.network.down, binary, True)}; upload: {quantity(s.network.up, binary, True)}"]
        if s.usage.started_on:
            lines.append(f"Usage tracking started: {s.usage.started_on}; initial periods may be partial.")
        if s.usage.notice:
            lines.append(s.usage.notice)
        return "\n".join(lines)

    def tooltip(self, widget, x, y, keyboard, tooltip):
        tooltip.set_text(self.summary())
        return True

    def draw_card(self, widget, cr):
        appearance = self.config["appearance"]
        theme = THEMES[appearance["theme"]]
        accent = appearance["accent_color"]
        cyan = CYAN
        if appearance["theme"] == "light":
            # Preserve the chosen hue while giving thin text/graphs contrast.
            accent = "#" + "".join(f"{round(int(accent[i:i+2], 16)*.5):02X}" for i in (1, 3, 5))
            cyan = "#08768B"
        binary = appearance["units"] == "binary"
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.scale(appearance["scale"], appearance["scale"])
        rounded(cr, .5, .5, WIDTH-1, HEIGHT-1, RADIUS)
        color(cr, theme["background"], appearance["background_opacity"] if self.get_screen().is_composited() else 1)
        cr.fill_preserve()
        color(cr, theme["line"], .18)
        cr.set_line_width(1)
        cr.stroke()

        def text(value, x, y, size=12, tint=None, bold=False, right=False, width=None):
            layout = PangoCairo.create_layout(cr)
            font = Pango.FontDescription("Sans")
            font.set_absolute_size(size * Pango.SCALE)
            font.set_weight(Pango.Weight.SEMIBOLD if bold else Pango.Weight.NORMAL)
            layout.set_font_description(font)
            layout.set_text(value, -1)
            if width:
                layout.set_width(round(width * Pango.SCALE))
                layout.set_ellipsize(Pango.EllipsizeMode.END)
                layout.set_alignment(Pango.Alignment.RIGHT if right else Pango.Alignment.LEFT)
            tw = width if width else layout.get_pixel_size()[0]
            cr.move_to(x-tw if right else x, y)
            color(cr, tint or theme["text"])
            PangoCairo.show_layout(cr, layout)

        text("System", 16, 16, 15, bold=True)
        color(cr, theme["line"], .16)
        cr.move_to(16, 45)
        cr.line_to(304, 45)
        cr.stroke()
        s = self.sample
        now = s.time if s else time.monotonic()
        text("CPU", 16, 58, tint=theme["muted"])
        text(f"{s.cpu:.0f}%" if s and s.cpu is not None else "—", 16, 77, 17, bold=True)
        graph(cr, self.cpu.points, now, 126, 62, 178, 34, 100, accent, True)
        for label, metric, y in (("RAM", s.ram if s else None, 105),
                                 ("System disk", s.disk if s else None, 151)):
            text(label, 16, y, tint=theme["muted"])
            text(capacity(metric.used, metric.total, binary) if metric else "Unavailable" if s else "—",
                 304, y, 12, right=True)
            bar(cr, 16, y+28, 288, metric.fraction if metric else 0, accent, theme["line"])
        text("Weekly usage", 16, 201, tint=theme["muted"])
        text("Daily usage", 304, 201, tint=theme["muted"], right=True)
        text(quantity(s.usage.weekly if s else None, binary), 16, 220, 15, bold=True, width=136)
        text(quantity(s.usage.daily if s else None, binary), 304, 220, 15, bold=True, right=True, width=136)
        color(cr, theme["line"], .16)
        cr.move_to(160, 201)
        cr.line_to(160, 239)
        cr.stroke()
        text("Network", 16, 252, tint=theme["muted"])
        rate = s.network if s else None
        if rate and rate.status == "Ready":
            text("↓ " + quantity(rate.down, binary, True), 16, 273, 14, accent)
            text("↑ " + quantity(rate.up, binary, True), 304, 273, 14, cyan, right=True)
        else:
            text(rate.status if rate else "Warming up", 304, 252, 12, right=True)
            text("↓ —", 16, 273, 14, accent)
            text("↑ —", 304, 273, 14, cyan, right=True)
        color(cr, theme["line"], .13)
        cr.move_to(16, 317)
        cr.line_to(304, 317)
        cr.stroke()
        graph(cr, self.down.points, now, 16, 301, 288, 16, self.net_scale.value, accent, True)
        graph(cr, self.up.points, now, 16, 301, 288, 16, self.net_scale.value, cyan)
        return False
