# TallyDesklet 0.2.1

A compact GTK desktop widget for CPU, memory, filesystem capacity, network
throughput, and daily/weekly data usage. MIT licensed; no telemetry or accounts.

This release renames **Mint Meter** to **TallyDesklet**, including the repository,
application menu entry, package, and command. The `mint-meter` command remains
available for existing scripts and opt-in login entries.

<img src="https://raw.githubusercontent.com/saeedt20/tallydesklet/v0.2.1/docs/examples/dark.png" alt="Actual GTK interface rendered with illustrative example data" width="320">

The preview shows the real GTK interface with fixed example data, not a user's
live measurements. More previews and instructions are in the
[README](https://github.com/saeedt20/tallydesklet/blob/v0.2.1/README.md).

## Download and install

Download **tallydesklet_0.2.1-1_all.deb** and **SHA256SUMS** from the assets below,
then run in that directory:

```sh
sha256sum -c SHA256SUMS
sudo apt install ./tallydesklet_0.2.1-1_all.deb
tallydesklet
```

The package declares distribution-provided Python, GTK 3, Cairo, psutil, and
iproute2 dependencies. It targets Xfce/X11. Installation does not launch the
app or enable startup at login.

If upgrading, quit the old app with `mint-meter --quit` before installation.
Apt replaces the old package. First launch copies legacy preferences and usage
only when the new files are absent; original files remain intact. Existing
TallyDesklet state takes priority. Login startup stays opt-in.

## Features

- CPU and network histories; memory and disk capacity bars.
- Weekly and daily combined network usage, preserved across normal restarts.
- Dark/light themes, opacity, scaling, units, and refresh interval settings.
- Dragging, position locking, reset, workspaces, and always-on-top controls.
- Native settings, single-instance CLI, and opt-in login startup.

Usage totals count observed traffic while the app runs; they exclude traffic
while closed and ambiguous reconnect/reset/gap traffic. They are not ISP
billing totals. Daily reset is local midnight; weekly reset is Sunday midnight.

## Verification and limitations

The release workflow runs unit tests, isolated GUI smoke checks, desktop-entry
validation, and lintian before publishing. Real login startup, hardware hotplug,
and actual suspend/resume are not verified by virtual-display checks. Wayland
may ignore positioning and desktop-stacking hints. A `.deb` alone does not
establish compatibility with every Debian/Ubuntu release.
