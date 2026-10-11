#!/bin/bash
# Run the installer straight from a clone, without pip. Same options as
# arc-sidebar-install. See: ./install.sh --help
HERE="$(cd "$(dirname "$0")" && pwd)"
PYTHONPATH="$HERE" exec python3 -m arc_sidebar_for_firefox "$@"
