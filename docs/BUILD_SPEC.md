# TallyDesklet — Complete Build Brief for Claude Code or Codex

## 1. Your task

Act as the developer of this project. Build, test, document, and package a working Linux desktop system-monitor widget from this specification. Deliver runnable source code and an installable `.deb`, with a repository ready for GitHub.

Read this entire document before implementing. Inspect the actual development environment and any existing repository instructions. Make reasonable implementation decisions, record them briefly, and proceed through the work. Do not stop at a plan, static mockup, or partial scaffold. Ask questions only when a missing decision genuinely blocks progress. Do not claim that a test, installation, or desktop behavior was verified unless it actually was.

The owner-selected name is **TallyDesklet**, package and command `tallydesklet`, current version `0.2.1`. The earlier name was Mint Meter. Use original artwork and no Apple branding.

On first launch, import legacy `mint-meter` preferences and usage only when the
new `tallydesklet` file is absent, preserving the original files. Keep the
`mint-meter` command as a compatibility launcher. Preserve existing opt-in
autostart; installation must never enable it.

## 2. Product purpose and design

- Target desktop: **Linux Mint 22.3 Xfce**.
- Purpose: glance at current CPU, RAM, system disk storage, and network transfer rates directly on the desktop.
- Visual direction: macOS-inspired rounded card, translucent dark background, restrained mint and cyan accents, clean type, small graphs.
- Use a small card in the upper-right corner.
- Place **system disk usage beneath RAM**, in the same style.
- Deliver one combined compact widget. Do not expand it into a large dashboard or four separate windows.
- Longer-term goal: distribute an installable `.deb` and share the project through GitHub.

Use the logical dimensions below rather than scaling the widget as a fraction of screen resolution. This document is sufficient to implement the design without a desktop reference screenshot.

The wallpaper and Xfce panel in the mockup provide context only. Do not change the user's wallpaper, panel, theme, compositor, or desktop icons.

## 3. Scope and priorities

### Required for version 0.1

1. Real CPU, RAM, root-filesystem storage, download, and upload measurements.
2. Compact translucent desktop card matching the agreed design.
3. CPU and network history graphs; RAM and disk capacity bars.
4. Position dragging, position locking, persistent settings, and reset-position command.
5. Default below ordinary windows; optional always-on-top behavior.
6. Settings for appearance, interval, network interface, disk path, and login startup.
7. Graceful handling of missing data, reconnects, suspend/resume, and display changes.
8. A normal application-menu launcher, single-instance behavior, and a way to quit.
9. Automated tests for meaningful logic, a desktop verification checklist, and a built `.deb`.
10. README, build instructions, CI configuration, and release instructions.

### Required for version 0.2 (owner-approved, 2026-10-08)

1. Add a two-column data-usage row immediately above Network: **weekly usage
   on the left, daily usage on the right**. Keep one compact 320 × 330 logical-pixel card.
2. Each total combines download and upload byte-counter deltas on the currently
   selected network interface, without summing overlapping interfaces.
3. Daily totals reset at local midnight; calendar-week totals reset at **Sunday
   local midnight**. Initial periods contain only traffic observed since tracking began.
4. Count while TallyDesklet runs; preserve totals across normal quit/restart,
   but do not include traffic while closed or imply full-system/billing accounting.
5. Persist at most seven daily aggregate buckets atomically under
   `$XDG_STATE_HOME/tallydesklet/usage.json` (default `~/.local/state/tallydesklet/usage.json`).
   Checkpoint at most once per minute and flush changed totals on normal shutdown.
6. Establish a fresh baseline on app launch, interface switch, unavailable
   counters, counter reset, nonpositive elapsed time, or sampling gaps over 15
   seconds. Exclude unobserved/ambiguous traffic rather than estimate it.
   Assign a valid delta crossing midnight to the day of the later sample.
7. Respect decimal/binary units, retain totals while offline, surface persistence
   failures, preserve corrupt history, and test rollovers, restart and reset behavior.

### Later, optional enhancements

CPU temperature, battery state, per-core details, disk I/O, GPU statistics, separate cards, process lists, alerts, and a tray icon. They must not delay the complete first version. Temperature and other hardware-specific features must show unavailable states when unsupported.

### Out of scope

Accounts, cloud services, AI features, telemetry, remote monitoring, background web servers, automatic updates, a replacement desktop shell, and compositor replacement for blur.

## 4. Technology and environment

Recommended implementation: **Python 3 + GTK 3/PyGObject + Cairo + psutil**. GTK 3 is a deliberate default for an Xfce/X11 desktop utility with window-positioning and stacking controls. Use distribution packages compatible with the target OS instead of assuming the newest upstream APIs exist.

- Use the system Python and normal distribution-provided dependencies.
- Use Cairo for lightweight custom graphs/background drawing where useful, and accessible GTK controls for settings.
- Avoid Electron, an embedded browser, and a web frontend for this small utility.
- Keep metric collection and formatting independent of GTK so they can be tested without a display.
- An interpreted Python app can be packaged in a `.deb`; native compilation is not required.
- Target X11 first. Inspect the actual session rather than assuming it. Clearly document limitations on Wayland and do not claim full Wayland desktop-widget support without testing.
- Detect `/etc/os-release`, Python/GTK/psutil versions, session type, display availability, and packaging tools. Report meaningful incompatibilities.
- Do not silently replace a previously chosen stack in an existing repository. Explain any necessary deviation.

Expected runtime dependencies to verify on the target distribution: `python3`, `python3-gi`, `python3-gi-cairo`, `python3-cairo`, `python3-psutil`, and `gir1.2-gtk-3.0`. Determine the actual Debian package metadata from the implementation rather than copying unverified version constraints.

## 5. Visual specification

### Geometry and styling

| Property | Default target |
| --- | --- |
| Card size | 320 × 330 logical pixels for version 0.2, including the data-usage row |
| Position | Upper-right of the selected monitor's usable work area |
| Edge margin | 24 logical pixels, clear of desktop panels |
| Inner padding | 16 logical pixels |
| Corner radius | 16–18 logical pixels |
| Background | Charcoal around `#14252E`, approximately 90% opacity |
| Main text | Off-white around `#F0F5F7` |
| Secondary text | Muted gray around `#B8C5CC` |
| Primary accent | Mint around `#5FE3AF` |
| Upload accent | Cyan around `#3BCBE8` |
| Borders/dividers | Very subtle low-opacity light lines |
| Type | Installed system sans-serif; no proprietary fonts |
| Header | `System`, approximately 14–15 px semibold, with a small gear button |
| Body | Approximately 12–13 px labels, 14–16 px values |
| Graph strokes | Approximately 1–1.5 logical pixels, with restrained area fill |
| Progress bars | Approximately 6–8 logical pixels tall, rounded ends |

Use these as design tokens rather than scattering literal values throughout the app. Preserve legibility at 100% and 200% display scaling. Provide a scale setting rather than sizing the card as a percentage of the screen. Avoid layout jitter as numbers change.

Translucency is enough. True wallpaper blur is not a requirement. If compositing is unavailable, use a readable opaque fallback. Apply opacity to the background, not to the entire window and its text. Keep decoration and shadows understated.

### Content order

| Section | Left content | Right content / visualization |
| --- | --- | --- |
| Header | `System` | Gear button |
| CPU | `CPU`, current total percentage | Tiny 60-second sparkline |
| RAM | `RAM`, used / total capacity | Thin capacity bar |
| System disk | `System disk`, used / total capacity | Thin capacity bar |
| Data usage | `Weekly usage`, combined byte total | `Daily usage`, combined byte total |
| Network | `Network`, separate down/up speeds | Small dual-series history graph |

Network labels must remain understandable without color: `↓` is download and `↑` is upload. Use mint for download and cyan for upload consistently. Tooltips may explain values, but essential information must remain visible.

Examples such as `24%`, `6.2 / 16 GB`, `128 / 512 GB`, `↓ 3.8 MB/s`, and `↑ 420 KB/s` are illustrative only. Never ship them as live values. Real measurements replace them immediately after sampling initialization.

No oversized icons, giant title, repeated legend, explanatory footer, or permanent per-core table. Prioritize a small footprint and clear values.

## 6. Metric definitions and sampling

Use a monotonic clock for elapsed time. Avoid blocking collection on the GTK event loop. Keep histories bounded and update only when necessary. Default CPU/RAM/network sampling to 1 second, disk to 10 seconds. Offer 0.5, 1, 2, and 5-second intervals for the fast metrics.

### CPU

- Display aggregate utilization on a 0–100% scale across all cores.
- A nonblocking `psutil.cpu_percent(interval=None)` approach is suitable. Prime the sampler and treat the first result as warm-up rather than a valid measurement.
- Keep the last 60 seconds of timestamped history, including when the refresh interval changes.
- Use a fixed 0–100% graph range.

### RAM

- Use `psutil.virtual_memory()`.
- Define displayed used memory as `total - available`, so reclaimable memory is handled sensibly.
- Calculate the bar using that same used/total definition.
- Show used and total capacity; put the percentage and available capacity in a tooltip if space is tight.
- Do not mix a different definition of used memory into the label and bar.

### System disk

- Default monitored path: `/`.
- Use `psutil.disk_usage(path)` or an equivalent filesystem-capacity API.
- This means occupied storage on the root filesystem, **not disk read/write speed or the sum of all physical drives**.
- Display actual occupied bytes and total filesystem capacity. Fill the bar with `used / total` so it agrees with the visible numbers.
- Report space available to the current user in a tooltip; reserved filesystem blocks can make this differ from `total - used`. Do not silently conflate these measures.
- Permit another existing local path in settings; explain that its containing filesystem is measured.
- Handle inaccessible/unmounted paths without crashing. Do not silently switch a user-selected missing filesystem to `/`.

### Network

- Obtain cumulative per-interface byte counters and derive rates from counter differences divided by measured elapsed seconds.
- Default to one active interface selected using the system's routing information. Support an explicit interface override and show the selected name in a tooltip/settings.
- Do not sum physical, tunnel, bridge, and loopback interfaces together, which can double-count traffic.
- Exclude loopback from automatic selection. Define and document VPN behavior: prefer the routed logical interface where appropriate, with a manual physical-interface override.
- If multiple routes are candidates, use a deterministic preference and document it. Avoid interface flapping.
- Use safe APIs or subprocess argument arrays for route inspection; avoid shell interpolation and fragile parsing of localized output.
- Handle Wi-Fi/Ethernet changes, IPv4/IPv6 route availability, no active route, interface removal, counter reset, suspend/resume, and elapsed intervals of zero or less.
- Reset baselines after an interface change or long sampling gap. Never show a negative rate or a huge artificial reconnect spike.
- Display current throughput, not negotiated link speed or an internet speed-test result. Generate no external network traffic to obtain measurements.
- Use a shared graph scale for upload/download, with a nonzero floor and gradual scale adjustment. Show both traces clearly.
- Distinguish `Offline`, `Unavailable`, and a valid idle `0 B/s` where detectable.

### Units and formatting

Default to decimal `GB`, `MB/s`, and `KB/s` to match the concept. Convert using powers of 1000. If a binary-units setting is supplied, use `GiB`, `MiB/s`, and `KiB/s` with powers of 1024. Never label binary quantities as decimal units. Keep numeric widths stable, choose sensible precision, and do not label bytes/second as bits/second.

API details and available fields must be verified against the installed psutil version. Keep formatting, selection, and sampling policies independently testable.

## 7. Desktop integration and interaction

- Start without stealing keyboard focus. Remain above the wallpaper but below ordinary application windows by default.
- Do not reserve screen space or alter maximized-window geometry.
- Hide the widget itself from the taskbar and workspace pager where supported; settings should behave like an ordinary accessible dialog.
- Show on all workspaces by default, with a toggle if feasible.
- Left-drag the header to move when unlocked. Save the position after movement, not on every mouse event.
- Locking position must still leave settings and the context menu accessible.
- Gear button and right-click menu should provide Settings, Lock/Unlock position, Always on top, Reset position, and Quit.
- Always-on-top and keep-below must not be set simultaneously.
- Preserve monitor preference and position; clamp to an available work area if a monitor disappears or the resolution changes. Support negative monitor coordinates.
- Launching the app twice must reuse the existing instance. A second launch may open settings so a misplaced or hidden widget remains recoverable.
- Provide commands `tallydesklet`, `tallydesklet --settings`, `tallydesklet --reset-position`, `tallydesklet --quit`, and `tallydesklet --version`.
- Provide keyboard access to settings controls and accessible names for icon-only buttons. Support Escape to close settings.

Treat X11 window hints as requests, not guarantees. Select the GTK/GDK window type and stacking strategy by testing with Xfce's window manager and desktop. In particular, verify that clicking the desktop and using Show Desktop do not permanently bury or lose the widget. Avoid an override-redirect shortcut that breaks input or reliable window management. Do not use a dock reservation to simulate a desktop widget.

## 8. Settings and persistence

Use `$XDG_CONFIG_HOME/tallydesklet/config.json`, falling back to `~/.config/tallydesklet/config.json`. Store optional bounded logs under the XDG state directory. No writes into the installed application directory.

Suggested schema, adjustable to the implementation:

```json
{
  "schema_version": 1,
  "appearance": {
    "theme": "dark",
    "background_opacity": 0.9,
    "scale": 1.0,
    "accent_color": "#5FE3AF",
    "units": "decimal"
  },
  "sampling": {
    "interval_seconds": 1.0,
    "history_seconds": 60,
    "disk_interval_seconds": 10
  },
  "network": { "interface": "auto" },
  "disk": { "path": "/" },
  "window": {
    "monitor": "primary",
    "anchor": "top-right",
    "margin": 24,
    "position": null,
    "locked": false,
    "always_on_top": false,
    "all_workspaces": true
  }
}
```

Offer dark and light themes, opacity, scale, refresh interval, interface choice, disk path, position lock, always-on-top, and startup at login. Settings may use a larger ordinary dialog; the main card must stay compact.

Validate values, enforce safe bounds, use atomic saves, and recover from malformed config by preserving the bad file and loading defaults. Apply settings without needing to restart where practical. Avoid excessive writes and never write samples to disk continuously.

Startup at login is off until enabled. Use a user-scoped XDG autostart entry; remove/disable it when switched off. Derive its actual state from the entry to avoid two conflicting sources of truth. Installation itself must not start the app as root or silently turn on autostart. If a development checkout cannot supply a stable executable path, explain the limitation until installed.

## 9. Suggested repository structure

Use the following paths as a guide; keep modules small and avoid unnecessary abstractions.

| Path | Responsibility |
| --- | --- |
| `README.md` | Features, screenshot, supported target, install/run/uninstall instructions |
| `pyproject.toml` | Project metadata and test/lint configuration |
| `src/tallydesklet/__init__.py` | Package metadata |
| `src/tallydesklet/__main__.py` | Module entry point |
| `src/tallydesklet/app.py` | Application lifecycle, CLI, single instance |
| `src/tallydesklet/metrics.py` | CPU, memory, filesystem collection |
| `src/tallydesklet/network.py` | Interface selection, counters, rate calculation |
| `src/tallydesklet/history.py` | Timestamped bounded series |
| `src/tallydesklet/formatting.py` | Units and compact labels |
| `src/tallydesklet/config.py` | Validation, persistence, migrations |
| `src/tallydesklet/autostart.py` | User startup entry management |
| `src/tallydesklet/ui/widget.py` | Main card and desktop behavior |
| `src/tallydesklet/ui/graphs.py` | Cairo graphs and bars |
| `src/tallydesklet/ui/settings.py` | Preferences dialog |
| `src/tallydesklet/ui/theme.py` | Design tokens, light/dark styling |
| `data/tallydesklet.desktop` | Application-menu launcher |
| `data/icons/` | Original app icon assets |
| `debian/` | Debian packaging metadata and rules |
| `scripts/dev-run.sh` | Development launch using system dependencies |
| `scripts/build-deb.sh` | Repeatable package build |
| `tests/` | Focused unit and integration tests |
| `docs/DESIGN.md` | Visual choices and implementation notes |
| `docs/TESTING.md` | Tested environments, manual checklist, limitations |
| `docs/RELEASING.md` | Versioning, build, checksums, GitHub instructions |
| `docs/screenshots/` | Actual app screenshots when available |
| `.github/workflows/ci.yml` | Tests and packaging checks |
| `.github/workflows/release.yml` | Tag-triggered release artifact workflow |
| `.gitignore` | Exclude builds, caches, local settings, credentials |
| `CHANGELOG.md` | User-facing release history |
| `LICENSE` | Only the owner's chosen license |

Keep this specification in the repository as `docs/BUILD_SPEC.md`. Add a concise `AGENTS.md` with the verified run, test, and build commands. Avoid maintaining conflicting copies of project requirements.

## 10. Packaging and distribution

- Prefer conventional Debian packaging with debhelper and appropriate Python helpers. A build script should produce `dist/tallydesklet_0.2.1-1_all.deb` for version 0.2 or the correct architecture-specific equivalent.
- Use `Architecture: all` only if the shipped app/assets are architecture-independent and native libraries are declared system dependencies. Do not bundle architecture-specific binaries under an `all` label.
- Provide correct dependencies, version, description, maintainer metadata, desktop entry, and icon installation.
- Use `/usr/bin/tallydesklet` as the launcher. Install private modules/resources consistently under standard Debian paths; do not depend on the build checkout or current working directory.
- Build as an ordinary user; use appropriate fakeroot/root-owner handling for package ownership. Avoid unnecessary maintainer scripts.
- Use one authoritative application version and synchronize package/release versions.
- The app must run offline after dependencies are installed; no runtime downloads or `pip install` on launch.
- Check package contents and metadata with Debian tooling. Run lintian if available and explain material findings.
- Verify installation, launching, upgrade, and removal in an appropriate disposable target environment where possible. Never remove unrelated user software to satisfy a test.
- Document that a `.deb` does not automatically guarantee compatibility with every Debian/Ubuntu release.

Expected user installation form, after substituting the actual artifact filename:

```bash
sudo apt install ./tallydesklet_0.2.1-1_all.deb
tallydesklet
```

Uninstallation should use the package manager. Explain separately how to disable/remove the user autostart entry and optionally delete user configuration. Package removal must not silently delete personal settings.

Prepare GitHub-ready source, a `.deb` release asset, and SHA-256 checksums. Keep built packages out of source control; upload them as release assets. README screenshots must show the real implementation, not imply that the concept image is a working screenshot.

The owner has expressed an intent to share on GitHub but has not supplied an account, repository, license, or final publication instructions in this brief. Complete local development and prepare the release first. Do not invent a remote, publish under an assumed identity, or assign a license without the owner's decision. If publication is explicitly authorized in the live session, use the supplied repository and normal authentication. Otherwise give the exact remaining steps. Never commit credentials, machine-specific personal data, or config files.

CI should run meaningful tests and build the package against a compatible baseline, with GUI smoke checks under a virtual display where useful. A headless smoke test is not proof of Xfce desktop integration. A release workflow may build and attach artifacts on an explicitly pushed version tag; scope write permissions to that job and document the trigger. Verify current action versions when implementing.

## 11. Reliability and performance

- Run as an ordinary user. Reading these metrics must not require sudo or a privileged background service.
- Do not block GTK with sleeps, long-running subprocesses, or disk/network operations.
- Keep sample history and log files bounded; clean up timers/resources on exit.
- Avoid frequent shell subprocesses for information available through psutil or stable local APIs.
- Stop unnecessary redraws when possible. Do not animate at 60 FPS for once-per-second data.
- Aim for less than 1% of one CPU core on average at the default interval and around 100 MiB RSS or less on a typical desktop. These are engineering targets, not promises; measure and report CPU convention, hardware, sampling interval, and limitations.
- Run a sustained session to check for growing memory usage and error spam. Missing optional information should produce a calm unavailable state, not repeated popups.
- Error handling must not replace failed live readings with fictional data.
- If adding a demo mode for visual testing, make it explicit and never enable it by default.

## 12. Verification and acceptance criteria

### Automated tests

Cover high-value logic with deterministic fixtures:

- Memory calculation and matching progress bar values.
- Filesystem used/total versus user-available space, missing path handling.
- Decimal/binary conversions, rate formatting, zero and large values.
- Rate calculation for known byte deltas and elapsed times.
- First sample, counter reset, interface switch, no route, and resume gaps.
- Interface selection without double-counting tunnel and physical traffic.
- History eviction by time at different sampling intervals.
- Config validation, malformed-file recovery, and atomic persistence.
- Monitor-position clamping, including negative coordinates.
- Autostart entry creation/removal in temporary XDG directories.

Use injected data and temporary directories. Unit tests must not modify real user settings or depend on a particular network adapter. Add a GUI launch/quit smoke test if the environment supports it.

### Manual desktop checks

- [ ] Main card is compact, 320 × 330 logical pixels for version 0.2, with no clipping or oversized sections.
- [ ] All four sections appear in order: CPU, RAM, System disk, Network.
- [ ] Labels, units, bars, and graphs remain legible at 100% and 200% scale.
- [ ] CPU reacts to load; RAM and disk values agree with the documented definitions.
- [ ] Network responds to traffic without negative values, reconnect spikes, or double counting.
- [ ] Drag, lock, reset position, and restart persistence work.
- [ ] No duplicate instance appears on repeated launch.
- [ ] Desktop layering, workspace switching, Show Desktop, and always-on-top work on Xfce.
- [ ] Widget does not steal focus or reserve maximized-window space.
- [ ] Settings remain accessible when position is locked.
- [ ] Opaque fallback is readable with compositing disabled.
- [ ] Monitor removal, resolution change, and suspend/resume are handled.
- [ ] Autostart opt-in works on the next login and can be disabled.
- [ ] Installed launcher and icon work outside the repository directory.
- [ ] `.deb` installation, upgrade, and removal behave correctly.
- [ ] Sustained runtime shows no unbounded history, memory growth, or repetitive error logging.

Record each check as passed, failed, or not tested, with environment details. If Mint 22.3 Xfce is unavailable, complete everything feasible and clearly identify the desktop checks still needing that machine. Do not call a build artifact fully target-tested based on a container alone.

## 13. Implementation sequence

1. Inspect environment and repository. Record assumptions and choose a minimal implementation plan.
2. Implement independent sampling, formatting, history, and configuration logic with focused tests.
3. Build the compact card with live data. Validate size early so the widget does not become too large.
4. Implement desktop integration, settings, persistence, autostart, and recovery commands.
5. Exercise edge cases and compare a real screenshot to the design specification/reference.
6. Build and inspect the `.deb`; test installation where possible.
7. Finish documentation, CI, changelog, and release assets.
8. Deliver the runnable result, verification evidence, exact commands, and any remaining environment-specific limitations.

If a task is blocked, finish all independent work and state the specific blocker. Do not replace a working app with only screenshots or suggested code snippets.

## 14. Final response expected from the coding agent

Provide a concise report containing:

1. What was built and where the source lives.
2. The `.deb` artifact path and checksum file.
3. Verified install, launch, settings, test, build, and uninstall commands.
4. A screenshot of the actual application if possible.
5. Tests run, target environment used, and any unverified desktop behavior.
6. Measured resource use if measured; do not invent numbers.
7. GitHub publication status or the concrete remaining owner decisions.

## 15. Primary implementation references

Consult the installed versions and current primary documentation during implementation:

- [PyGObject GTK 3 resources](https://pygobject.gnome.org/tutorials/gtk3.html)
- [GTK 3 window API](https://docs.gtk.org/gtk3/class.Window.html)
- [GTK keep-below behavior and window-manager caveats](https://docs.gtk.org/gtk3/method.Window.set_keep_below.html)
- [GTK window type hints](https://docs.gtk.org/gtk3/method.Window.set_type_hint.html)
- [psutil API reference](https://psutil.readthedocs.io/stable/)
- [Xfce documentation](https://docs.xfce.org/)
- [Debian Policy](https://www.debian.org/doc/debian-policy/)
- [Desktop Entry Specification](https://specifications.freedesktop.org/desktop-entry-spec/latest/)
- [Desktop Application Autostart Specification](https://specifications.freedesktop.org/autostart-spec/latest/)

The product choices, dimensions, defaults, project name, performance targets, and suggested structure above are implementation guidance derived from the conversation. They are not claims that the app already exists or that these targets have already been verified.
