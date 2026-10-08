"""Pure logical-coordinate placement; monitors may have negative origins."""


def place(area, size, position=None, margin=24):
    x, y, width, height = area
    w, h = size
    px, py = position if position is not None else (x + width - w - margin, y + margin)
    return (round(max(x, min(px, x + max(0, width - w)))),
            round(max(y, min(py, y + max(0, height - h)))))
