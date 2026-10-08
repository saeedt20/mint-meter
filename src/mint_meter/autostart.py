"""Opt-in, user-scoped XDG autostart. No installation side effects."""
import configparser
from pathlib import Path

from .config import atomic_write, config_home


def entry_path():
    return config_home() / "autostart/mint-meter.desktop"


def enabled(path=None):
    path = Path(path) if path else entry_path()
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(path)
        group = parser["Desktop Entry"]
        return (not group.getboolean("Hidden", fallback=False) and
                group.getboolean("X-GNOME-Autostart-enabled", fallback=True) and
                bool(group.get("Exec")))
    except (KeyError, ValueError, configparser.Error):
        return False


def set_enabled(value, path=None, executable="/usr/bin/mint-meter"):
    path = Path(path) if path else entry_path()
    if value:
        if not Path(executable).is_file():
            raise ValueError("Install the .deb first to enable login startup at /usr/bin/mint-meter.")
        # The production executable is fixed; tests can supply an isolated absolute path.
        escaped = str(executable).replace("\\", "\\\\").replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
        atomic_write(path, '[Desktop Entry]\nType=Application\nName=Mint Meter\n'
                     f'Exec="{escaped}"\nIcon=mint-meter\nTerminal=false\nHidden=false\n')
    else:
        path.unlink(missing_ok=True)
