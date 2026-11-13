"""Separate read-only operator observer; NEVER install with the WebJob.

Uses the operator's existing az login, not the Web App identity. No role changes,
deletion or shell execution. No raw CLI errors or inventory names are printed.
This does not make a laptop an independent cleanup executor.
"""

import json
import subprocess

from watchdog import API, GROUP, SERVER, SUB, TARGET


def confirm(run=subprocess.run):
    get = run(["az", "rest", "--method", "get", "--url", "https://management.azure.com" + TARGET + API,
               "--only-show-errors", "-o", "json"], capture_output=True, text=True, timeout=20)
    # Azure CLI does not expose an HTTP status structurally. Require its specific
    # Not Found / ResourceNotFound error, plus the separate successful inventory.
    absent = get.returncode != 0 and "Not Found(" in get.stderr and '"code":"ResourceNotFound"' in get.stderr.replace(" ", "")
    listed = run(["az", "sql", "db", "list", "--subscription", SUB, "-g", GROUP,
                  "-s", SERVER.rsplit("/", 1)[1], "--query", "[].id", "--only-show-errors", "-o", "json"],
                 capture_output=True, text=True, timeout=20)
    if listed.returncode:
        return {"arm_absent": absent, "inventory_absent": None, "confirmed": False}
    identifiers = json.loads(listed.stdout)
    if not isinstance(identifiers, list) or not identifiers or not all(isinstance(i, str) and i.lower().startswith(SERVER.lower() + "/databases/") for i in identifiers):
        return {"arm_absent": absent, "inventory_absent": None, "confirmed": False}
    inventory_absent = TARGET.lower() not in [i.lower() for i in identifiers]
    return {"arm_absent": absent, "inventory_absent": inventory_absent, "confirmed": absent and inventory_absent}


if __name__ == "__main__":
    try:
        from datetime import datetime, timezone
        result = confirm()
        print(json.dumps({"utc": datetime.now(timezone.utc).isoformat(), "target": TARGET, **result}, sort_keys=True))
        raise SystemExit(0 if result["confirmed"] else 1)
    except Exception:
        print('{"event":"OBSERVER_FAILED","confirmed":false}')
        raise SystemExit(1) from None
