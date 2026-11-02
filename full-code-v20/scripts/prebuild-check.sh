#!/usr/bin/env sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
echo "[V2.0] Checking required files..."
test -s "$ROOT/frontend/public/brand-logo.png" || {
  echo "ERROR: frontend/public/brand-logo.png is missing." >&2
  echo "Copy the original PNG from full-code-v15/frontend/public/brand-logo.png." >&2
  exit 1
}
test -s "$ROOT/backend/app/main.py"
test -s "$ROOT/backend/app/v20.py"
test -s "$ROOT/frontend/app/page.tsx"
test -s "$ROOT/deploy/Caddyfile"
test -s "$ROOT/compose.yaml"
if [ -f "$ROOT/.env" ]; then
  echo "WARNING: .env exists inside source tree; never commit secrets." >&2
fi
echo "[V2.0] Required files present."
