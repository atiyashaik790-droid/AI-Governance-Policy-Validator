#!/bin/sh
set -eu
# App Service/Oryx activates the deployment's existing Python environment.
# Never install drivers/dependencies, run migrations or print settings at startup.
exec python -m uvicorn app.hosting:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log
