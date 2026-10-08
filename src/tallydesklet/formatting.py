"""Consistent SI and IEC capacity / throughput labels."""


def quantity(value, binary=False, rate=False):
    if value is None:
        return "—"
    base = 1024 if binary else 1000
    units = ("B", "KiB", "MiB", "GiB", "TiB", "PiB") if binary else (
        "B", "KB", "MB", "GB", "TB", "PB")
    value = max(0, value)
    index = 0
    while value >= base and index < len(units) - 1:
        value /= base
        index += 1
    number = f"{value:.0f}" if index == 0 or value >= 100 else f"{value:.1f}"
    return f"{number} {units[index]}{'/s' if rate else ''}"


def capacity(used, total, binary=False):
    base = 1024 if binary else 1000
    units = ("B", "KiB", "MiB", "GiB", "TiB", "PiB") if binary else (
        "B", "KB", "MB", "GB", "TB", "PB")
    index = 0
    divisor = 1
    while total / divisor >= base and index < len(units) - 1:
        divisor *= base
        index += 1
    return f"{used / divisor:.1f} / {total / divisor:.1f} {units[index]}"
