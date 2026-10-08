"""Opt-in, user-scoped XDG autostart. No installation side effects."""
import configparser
from pathlib import Path

from .config import atomic_write, config_home


def entry_path():
    return config_home() / "autostart/tallydesklet.desktop"


def enabled(path=None):
    if path is not None:
        path = Path(path)
    else:
        path = entry_path()
        if not path.exists():
            path = config_home() / "autostart/mint-meter.desktop"
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(path)
        group = parser["Desktop Entry"]
        return (not group.getboolean("Hidden", fallback=False) and
                group.getboolean("X-GNOME-Autostart-enabled", fallback=True) and
                bool(group.get("Exec")))
    except (KeyError, ValueError, configparser.Error):
        return False


def set_enabled(value, path=None, executable="/usr/bin/tallydesklet"):
    default_path = path is None
    path = Path(path) if path is not None else entry_path()
    if value:
        if not Path(executable).is_file():
            raise ValueError("Install the .deb first to enable login startup at /usr/bin/tallydesklet.")
        # The production executable is fixed; tests can supply an isolated absolute path.
        escaped = str(executable).replace("\\", "\\\\").replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
        atomic_write(path, '[Desktop Entry]\nType=Application\nName=TallyDesklet\n'
                     f'Exec="{escaped}"\nIcon=tallydesklet\nTerminal=false\nHidden=false\n')
    else:
        path.unlink(missing_ok=True)
    # Only an explicit user choice changes login startup. The legacy launcher
    # remains installed so an existing opt-in entry works before this choice.
    if default_path:
        (config_home() / "autostart/mint-meter.desktop").unlink(missing_ok=True)
