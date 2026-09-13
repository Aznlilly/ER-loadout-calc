#!/usr/bin/env bash
# Serves this folder locally and opens it in your browser.
set -e
cd "$(dirname "$0")"

PORT="${1:-8000}"
URL="http://localhost:${PORT}/"

PYCMD=""
if command -v python3 >/dev/null 2>&1; then
  PYCMD=python3
elif command -v python >/dev/null 2>&1; then
  PYCMD=python
else
  echo "Python was not found on your PATH. Install Python 3 and try again." >&2
  exit 1
fi

echo "Starting the Elden Ring Loadout Optimizer at ${URL}"
echo "Press Ctrl+C to stop the server."

( sleep 1
  if command -v open >/dev/null 2>&1; then open "$URL"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"
  fi
) &

exec "$PYCMD" -m http.server "$PORT"
