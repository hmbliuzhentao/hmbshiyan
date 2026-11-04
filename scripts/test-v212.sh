#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
bash scripts/test-v21.sh
python tests/test_v211_admin_merchant_creation.py
python tests/test_v212_domain_roles.py
python - <<'PY'
import yaml
with open('compose.yaml', encoding='utf-8') as f:
  d=yaml.safe_load(f)
assert d['volumes']['heimanbo_v20_db']['name']=='heimanbo_v20_db'
assert d['volumes']['heimanbo_v20_videos']['name']=='heimanbo_v20_videos'
assert set(d['services'])=={'db','backend','frontend'}
print('PASS unchanged PostgreSQL and video volume names')
PY
