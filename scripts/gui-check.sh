#!/bin/sh
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export GTK_USE_PORTAL=0 GIO_USE_VFS=local NO_AT_BRIDGE=1
TALLYDESKLET_COMPOSITOR=off
if [ "${1:-}" = "--composited" ]; then
  TALLYDESKLET_COMPOSITOR=on
  shift
fi
export TALLYDESKLET_COMPOSITOR
TALLYDESKLET_TEST_SCREEN=1600x1000x24
if [ "${1:-}" = "--hidpi" ]; then
  export GDK_SCALE=2
  TALLYDESKLET_TEST_SCREEN=3200x2000x24
  shift
fi
TEST_CONFIG=$(mktemp -d /tmp/tallydesklet-wm-XXXXXX)
export XDG_CONFIG_HOME="$TEST_CONFIG"
# A private D-Bus session and X display are mandatory; this does not touch the real desktop.
exec dbus-run-session --config-file="$PROJECT_DIR/tests/session.conf" -- xvfb-run -a -s "-screen 0 $TALLYDESKLET_TEST_SCREEN" sh -c '
  # Virtual displays do not provide a supported hardware GL vblank renderer.
  xfwm4 --compositor="$TALLYDESKLET_COMPOSITOR" --vblank=off >/tmp/tallydesklet-test-wm.log 2>&1 &
  wm=$!
  trap "kill $wm 2>/dev/null || true" EXIT
  project=$1
  shift
  /usr/bin/python3 "$project/tests/gui_smoke.py" "$@"
' sh "$PROJECT_DIR" "$@"
