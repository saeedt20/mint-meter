#!/usr/bin/python3
"""Isolated live GUI/CLI smoke test. Run under dbus-run-session + Xvfb.

Needs xdotool; never run this test against an existing user instance/bus.
"""
import json
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import psutil

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("GdkX11", "3.0")
from gi.repository import Gdk, GLib

ROOT = Path(__file__).resolve().parent.parent
COMMAND = [str(ROOT / "scripts/dev-run.sh")]


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=10).stdout.strip()


def windows(name):
    result = subprocess.run(["xdotool", "search", "--name", f"^{name}$"], capture_output=True, text=True)
    return result.stdout.split()


def await_window(name):
    for _ in range(60):
        found = windows(name)
        if found:
            return found[0]
        time.sleep(.1)
    raise AssertionError(f"No {name} window")


def geometry(window):
    values = run("xdotool", "getwindowgeometry", "--shell", window)
    return dict(line.split("=", 1) for line in values.splitlines())


def screenshot(window, path):
    g = geometry(window)
    # Capture the visible root rectangle: foreign-window surfaces can retain old
    # sizes when XIDs are reused after restart, cropping larger-scale screenshots.
    root = Gdk.get_default_root_window()
    factor = root.get_scale_factor()
    pixbuf = Gdk.pixbuf_get_from_window(root, int(g["X"]) // factor, int(g["Y"]) // factor,
                                      int(g["WIDTH"]) // factor, int(g["HEIGHT"]) // factor)
    assert pixbuf is not None
    pixbuf.savev(str(path), "png", [], [])


def drag(window):
    run("xdotool", "mousemove", "--window", window, "70", "25", "mousedown", "1",
        "sleep", "0.2", "mousemove_relative", "--", "-100", "80", "sleep", "0.2", "mouseup", "1")
    time.sleep(.9)


def desktop_checks(window, settings, env, config):
    state = run("xprop", "-id", window, "_NET_WM_STATE", "_NET_WM_WINDOW_TYPE", "_NET_WM_STRUT")
    assert "_NET_WM_STATE_BELOW" in state and "_NET_WM_STATE_ABOVE" not in state, state
    assert "_NET_WM_WINDOW_TYPE_DESKTOP" in state, state
    assert "_NET_WM_STATE_SKIP_TASKBAR" in state and "_NET_WM_STATE_SKIP_PAGER" in state, state
    assert "_NET_WM_STRUT(CARDINAL)" not in state, state
    run("xdotool", "windowactivate", "--sync", settings, "key", "alt+t", "alt+a")
    time.sleep(.3)
    state = run("xprop", "-id", window, "_NET_WM_STATE")
    assert "_NET_WM_STATE_ABOVE" in state and "_NET_WM_STATE_BELOW" not in state, state
    run("xdotool", "windowactivate", "--sync", settings, "key", "alt+t", "alt+l", "alt+a")
    time.sleep(.3)
    run("xdotool", "windowactivate", "--sync", settings, "key", "Escape")
    time.sleep(.3)
    assert not windows("TallyDesklet Settings"), "Settings did not close after Escape (lock)"
    before = geometry(window)
    drag(window)
    assert geometry(window) == before, f"Locked card moved: before={before}, after={geometry(window)}, config={config.read_text()}"
    subprocess.run(COMMAND + ["--settings"], env=env, check=True, timeout=10)
    settings = await_window("TallyDesklet Settings")
    run("xdotool", "windowactivate", "--sync", settings, "key", "alt+l", "alt+a")
    time.sleep(.3)
    run("xdotool", "windowactivate", "--sync", settings, "key", "Escape")
    time.sleep(.3)
    assert not windows("TallyDesklet Settings"), "Settings did not close after Escape (unlock)"
    drag(window)
    after = geometry(window)
    assert (after["X"], after["Y"]) != (before["X"], before["Y"]), f"Unlocked card did not move: {config.read_text()}"
    assert json.loads(config.read_text())["window"]["position"] is not None
    run("wmctrl", "-k", "on")
    time.sleep(.3)
    assert "IsViewable" in run("xwininfo", "-id", window)
    run("xdotool", "mousemove", "10", "10", "click", "1")
    run("wmctrl", "-k", "off")
    run("wmctrl", "-n", "2")
    run("wmctrl", "-s", "1")
    time.sleep(.3)
    assert "IsViewable" in run("xwininfo", "-id", window)
    run("wmctrl", "-s", "0")
    print("PASS Xfwm hints, top/below switching, drag/lock/save, Show Desktop, workspace switching", flush=True)


def soak(process, window, output):
    seconds = int(os.environ.get("TALLYDESKLET_SOAK_SECONDS", "0"))
    if not seconds:
        return
    p = psutil.Process(process.pid)
    cpu_start = sum(p.cpu_times()[:2])
    started = time.monotonic()
    rss = []
    for _ in range(seconds):
        rss.append(p.memory_info().rss)
        time.sleep(1)
    elapsed = time.monotonic() - started
    report = {"seconds": round(elapsed, 2), "interval_seconds": 1,
              "cpu_percent_one_core": round(100*(sum(p.cpu_times()[:2])-cpu_start)/elapsed, 3),
              "rss_mib_start": round(rss[0]/2**20, 2), "rss_mib_end": round(rss[-1]/2**20, 2),
              "rss_mib_max": round(max(rss)/2**20, 2), "logical_cpus": psutil.cpu_count()}
    (ROOT / "dist/resource-check.json").write_text(json.dumps(report, indent=2) + "\n")
    screenshot(window, output / "dark-1x.png")
    print("RESOURCE", json.dumps(report), flush=True)


def main():
    global COMMAND
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-root", type=Path)
    parser.add_argument("--proot", default="proot")
    options = parser.parse_args()
    if options.installed_root:
        prefix = options.installed_root
        COMMAND = [options.proot, "-b", f"{prefix}/usr/share/tallydesklet:/usr/share/tallydesklet",
                   "-b", f"{prefix}/usr/bin/tallydesklet:/usr/bin/tallydesklet", "-w", "/tmp", "/usr/bin/tallydesklet"]
    output = ROOT / "dist/gui-screenshots"
    if options.installed_root:
        output = ROOT / "dist/installed-screenshots"
    elif os.environ.get("GDK_SCALE") == "2":
        output = ROOT / "dist/hidpi-screenshots"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tallydesklet-gui-") as temp:
        env = dict(os.environ, XDG_CONFIG_HOME=temp, XDG_STATE_HOME=temp)
        log = Path(temp) / "stderr.log"
        for theme, scale in (("dark", 1), ("light", 1), ("dark", 2)):
            config = Path(temp) / "tallydesklet/config.json"
            usage_file = Path(temp) / "tallydesklet/usage.json"
            config.parent.mkdir(exist_ok=True)
            config.write_text(json.dumps({"appearance": {"theme": theme, "scale": scale}}))
            with log.open("w") as stream:
                process = subprocess.Popen(COMMAND, env=env, stdout=stream, stderr=stream)
                try:
                    window = await_window("TallyDesklet")
                    time.sleep(3)
                    # The WM starts alongside this process; dispatch compositor
                    # selection changes before querying GDK's cached state.
                    context = GLib.MainContext.default()
                    while context.pending():
                        context.iteration(False)
                    assert process.poll() is None, log.read_text()
                    active = run("xprop", "-root", "_NET_ACTIVE_WINDOW")
                    assert hex(int(window)) not in active, "Widget stole focus"
                    g = geometry(window)
                    screen_scale = int(os.environ.get("GDK_SCALE", "1"))
                    assert (int(g["WIDTH"]), int(g["HEIGHT"])) == (320*scale*screen_scale, 330*scale*screen_scale), g
                    composited = Gdk.Screen.get_default().is_composited()
                    assert composited == (os.environ.get("TALLYDESKLET_COMPOSITOR") == "on"), "Unexpected compositor state"
                    screenshot(window, output / f"{theme}-{scale}x.png")
                    if theme == "dark" and scale == 1:
                        soak(process, window, output)
                    subprocess.run(COMMAND + ["--settings"], env=env, check=True, timeout=10)
                    settings = await_window("TallyDesklet Settings")
                    subprocess.run(COMMAND, env=env, check=True, timeout=10)
                    assert len(windows("TallyDesklet")) == 1
                    assert len(windows("TallyDesklet Settings")) == 1
                    screenshot(settings, output / "settings.png")
                    if theme == "dark" and scale == 1:
                        desktop_checks(window, settings, env, config)
                        saved_geometry = geometry(window)
                        subprocess.run(COMMAND + ["--quit"], env=env, check=True, timeout=10)
                        assert process.wait(timeout=10) == 0
                        usage_before = json.loads(usage_file.read_text())
                        assert usage_before["schema_version"] == 1
                        assert 1 <= len(usage_before["days"]) <= 7
                        assert all(type(v) is int and v >= 0 for v in usage_before["days"].values())
                        process = subprocess.Popen(COMMAND, env=env, stdout=stream, stderr=stream)
                        window = await_window("TallyDesklet")
                        time.sleep(.3)
                        restored = geometry(window)
                        assert (restored["X"], restored["Y"]) == (saved_geometry["X"], saved_geometry["Y"])
                        usage_after = json.loads(usage_file.read_text())
                        assert usage_after["started_on"] == usage_before["started_on"]
                        assert all(usage_after["days"].get(day, 0) >= value for day, value in usage_before["days"].items())
                        print("PASS saved usage totals survive process restart", flush=True)
                        print("PASS dragged position restored after process restart", flush=True)
                    else:
                        run("xdotool", "windowactivate", "--sync", settings, "key", "Escape")
                    time.sleep(.2)
                    assert not windows("TallyDesklet Settings"), "Escape did not close settings"
                    subprocess.run(COMMAND + ["--reset-position"], env=env, check=True, timeout=10)
                    assert json.loads(config.read_text())["window"]["position"] is None
                    subprocess.run(COMMAND + ["--quit"], env=env, check=True, timeout=10)
                    assert process.wait(timeout=10) == 0
                    errors = log.read_text()
                    assert "Traceback" not in errors and "CRITICAL" not in errors, errors
                    print(f"PASS {theme} {scale}x: geometry, screenshot, settings, single instance, Escape, reset, quit")
                    if errors:
                        print(errors)
                finally:
                    if log.read_text():
                        print(log.read_text(), flush=True)
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)


if __name__ == "__main__":
    main()
