#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python -m compileall -q backend
for test_file in \
  tests/test_v21_startup.py \
  tests/test_v21_auth_workspace.py \
  tests/test_v21_wechat_oauth.py \
  tests/test_v21_assignment_isolation.py \
  tests/test_v21_additive_migration.py \
  tests/test_merchant_order_v15.py; do
  echo "===== $test_file ====="
  python "$test_file"
done
