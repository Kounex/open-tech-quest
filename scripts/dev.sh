#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -e .env ]; then
  (umask 077; python3 -c 'import secrets; print("SECRET_KEY=" + secrets.token_hex(32))' > .env)
fi
if command -v docker >/dev/null 2>&1; then
  exec docker compose --env-file .env up --build "$@"
fi
exec podman compose --env-file .env up --build "$@"
