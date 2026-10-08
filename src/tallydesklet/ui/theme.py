"""Shared logical design tokens."""
WIDTH, HEIGHT, PADDING, RADIUS = 320, 330, 16, 18
CYAN = "#3BCBE8"
THEMES = {
    "dark": {"background": "#14252E", "text": "#F0F5F7", "muted": "#B8C5CC", "line": "#78909C"},
    "light": {"background": "#F1F7F6", "text": "#152C35", "muted": "#45616C", "line": "#78909C"},
}


def color(cr, value, alpha=1):
    cr.set_source_rgba(*(int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)), alpha)


def rounded(cr, x, y, w, h, radius):
    from math import pi
    radius = min(radius, w / 2, h / 2)
    cr.new_sub_path()
    for cx, cy, start in ((x+w-radius, y+radius, -pi/2), (x+w-radius, y+h-radius, 0),
                          (x+radius, y+h-radius, pi/2), (x+radius, y+radius, pi)):
        cr.arc(cx, cy, radius, start, start+pi/2)
    cr.close_path()
