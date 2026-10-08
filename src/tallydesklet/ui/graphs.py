from .theme import color, rounded


def bar(cr, x, y, width, fraction, accent, line):
    rounded(cr, x, y, width, 6, 3)
    color(cr, line, .18)
    cr.fill()
    if fraction and fraction > 0:
        rounded(cr, x, y, max(2, width * fraction), 6, 3)
        color(cr, accent, .9)
        cr.fill()


def graph(cr, points, now, x, y, width, height, maximum, accent, fill=False):
    cr.save()
    cr.rectangle(x, y, width, height)
    cr.clip()
    segments = []
    segment = []
    last = None
    for timestamp, value in points:
        if value is None or (last is not None and timestamp - last > 15):
            if segment:
                segments.append(segment)
            segment = []
        if value is not None:
            segment.append((x + width * (1 - (now-timestamp) / 60),
                            y + height * (1 - max(0, min(1, value / maximum)))))
        last = timestamp
    if segment:
        segments.append(segment)
    for segment in segments:
        if fill and len(segment) > 1:
            cr.move_to(segment[0][0], y+height)
            for point in segment:
                cr.line_to(*point)
            cr.line_to(segment[-1][0], y+height)
            cr.close_path()
            color(cr, accent, .10)
            cr.fill()
        cr.move_to(*segment[0])
        for point in segment[1:]:
            cr.line_to(*point)
        cr.set_line_width(1.4)
        color(cr, accent)
        cr.stroke()
    cr.restore()
