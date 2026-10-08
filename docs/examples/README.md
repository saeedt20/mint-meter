# Interface previews

`dark.png`, `light.png`, and `settings.png` capture the actual GTK widgets using
fixed, illustrative example data. They are not live readings and contain no
user desktop, hardware inventory, real interface names, or personal paths.

Only `scripts/render-examples.py` generates these curated previews. Ordinary
GUI smoke captures stay under ignored `dist/` and must never be copied here.
The normal application has no example-data mode.

To regenerate on an isolated virtual display with temporary preferences:

```sh
PREVIEW_XDG_DIR=$(mktemp -d)
XDG_CONFIG_HOME="$PREVIEW_XDG_DIR" XDG_STATE_HOME="$PREVIEW_XDG_DIR" \
  dbus-run-session --config-file=tests/session.conf -- \
  xvfb-run -a -s '-screen 0 1280x900x24' \
  /usr/bin/python3 scripts/render-examples.py
```

Use distribution GTK, Cairo, Xvfb and xauth dependencies. The renderer fixes the
GTK theme to Adwaita inside that temporary session. It starts no metric collector.
