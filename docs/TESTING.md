# Testing TallyDesklet

## Publication checks — version 0.2.1

All 44 deterministic unit tests passed during publication preparation. The
source launcher reports 0.2.1. Unit tests use injected counters and temporary
directories; they do not depend on a particular network adapter or write real
user preferences.

The local environment and historical performance reports are intentionally
kept private. No hardware model, host OS inventory, or live readings are
published here. This record makes no claim about a fresh target-system install.

```sh
PYTHONPATH=src /usr/bin/python3 -m unittest discover -s tests -v
./scripts/dev-run.sh --version
./scripts/build-deb.sh
(cd dist && sha256sum -c SHA256SUMS)
```

Coverage includes memory/bar agreement, disk reserved space, units, network
rates, route selection, warm-up, counter resets, interface switching, resume
gaps, bounded histories, atomic settings, monitor clamping, opt-in autostart,
combined usage totals, midnight/Sunday rollovers, bounded storage, restart,
corrupt-history recovery, and persistence failures.

Rename tests also cover importing legacy preferences and usage, preserving
original files, preferring new state, private file permissions, corrupt data,
failed imports, explicit paths, and preserving opt-in login startup choices.

The packaging regression test adds private files and live captures to a fixture
source tree and asserts that only allowlisted public documents enter the package.
The rootless build, checksum check, and desktop-entry validation also passed.

## Isolated GUI checks

```sh
sudo apt install xvfb xauth xfwm4 xdotool wmctrl x11-utils
./scripts/gui-check.sh
./scripts/gui-check.sh --composited
./scripts/gui-check.sh --hidpi
```

These commands start Xfwm on an isolated Xvfb display with a private D-Bus
session and temporary XDG config/state directories. Never run GUI automation
against a real user desktop session. Captures go into ignored `dist/`
directories because real readings can expose personal machine information.

Publication checks reran baseline, composited, and HiDPI isolated GUI checks,
including
dark/light themes, widget scales 1×/2×, positioning, saved usage, and CLI controls.
Source files, the staged Git index, and the extracted package passed redacted
Gitleaks scans. A separate review checked tracked filenames, public identity,
and the absence of host identifiers, personal paths, and private artifacts.

Historical virtual-display checks exercised geometry, dark/light themes,
scaling, focus, window hints, drag/lock/reset, single-instance forwarding,
Show Desktop, workspaces, settings, and saved usage after restart. Historical
results do not substitute for a fresh hosted CI run or physical-session testing.

## Physical-session acceptance checklist

- [ ] Fresh installation, upgrade, and removal with dependency resolution.
- [ ] Launcher and icon from the application menu.
- [ ] Real desktop clicks, Show Desktop, and workspace changes.
- [ ] Wi-Fi/Ethernet reconnect and VPN selection on hardware.
- [ ] Monitor hotplug and resolution changes.
- [ ] Actual suspend/resume.
- [ ] Opt-in startup on the next login and disabling it.
- [ ] Sustained runtime and resource use on representative hardware.

Virtual displays and deterministic fixtures do not prove hardware hotplug,
login startup, or suspend integration. No public performance guarantee is made.

## Continuous integration

GitHub Actions uses an Ubuntu 24.04 hosted runner to run unit tests, build a
rootless package, exercise isolated GUI checks, validate the desktop entry,
check package contents with lintian, and run the conventional debhelper build.
Consult the repository's Actions tab for actual run results.
