#!/bin/sh
# Flatpak launcher: the application and its Python dependencies live under /app.
export PYTHONPATH="/app/lib/gossip${PYTHONPATH:+:${PYTHONPATH}}"
exec python3 -m src.main "$@"
