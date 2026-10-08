#!/bin/sh
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_DIR"
PYTHONPATH=src /usr/bin/python3 -m unittest discover -s tests -v
exec /usr/bin/python3 scripts/package.py "$@"
