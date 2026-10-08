# TallyDesklet development

- Read `docs/BUILD_SPEC.md`; it is the sole copy of the requirements.
- Use distribution `/usr/bin/python3`, GTK 3, Cairo and psutil. No web frontend.
- Run: `./scripts/dev-run.sh`; version: `./scripts/dev-run.sh --version`.
- Unit tests: `PYTHONPATH=src /usr/bin/python3 -m unittest discover -s tests -v`.
- Build: `./scripts/build-deb.sh` (rootless, writes `dist/`).
- GUI smoke: `./scripts/gui-check.sh` with Xvfb, xauth, Xfwm4, xdotool, WMctrl
  and x11-utils installed. Add `--composited` or `--hidpi` for those checks.
  Always use its isolated X display, D-Bus session and temporary XDG preferences.
- Keep metric logic independent of GTK and histories bounded; never invent live readings.
- Do not alter user desktop settings, enable autostart by installation, or publish
  under an assumed identity. License and maintainer identity need owner decisions.
- Report exact verification environments; virtual displays do not prove hardware
  hotplug, real login startup, or suspend/resume integration.
