#!/bin/sh
set -eu
# Review package is DISABLED and has no deletion flag. No pip install or app edit.
watchdog_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 -I "$watchdog_dir/watchdog.py" --supervise --policy "$watchdog_dir/policy.json"
