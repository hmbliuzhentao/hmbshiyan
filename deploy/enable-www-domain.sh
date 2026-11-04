#!/usr/bin/env bash
# Run only after DNS points to the VPS, Caddy serves www, and ACR builds both www1 images.
# Keeps existing database, videos and Caddy container intact.
set -Eeuo pipefail
[ "$(id -u)" = 0 ] || { echo "Please run as root"; exit 1; }
SRC=/www/server/heimanbo-www
DST=/opt/heimanbo-v20
REG=crpi-ik4qgw7vjkd1ccwd.cn-hangzhou.personal.cr.aliyuncs.com/heimanbo
BACK="$REG/backend:v2.1.2-www1"
FRONT="$REG/frontend:v2.1.2-www1"
cd "$DST"
[ -f .env ] && [ -s compose.yaml ] || { echo "Existing .env or compose missing"; exit 1; }
[ -f "$SRC/deploy/compose.www.override.yaml" ] || { echo "Clone branch v2.1.2-www-domain into $SRC"; exit 1; }
for c in heimanbo-v20-backend heimanbo-v20-frontend heimanbo-v20-db heimanbo-test-caddy; do docker inspect "$c" >/dev/null; done
for v in heimanbo_v20_db heimanbo_v20_videos; do docker volume inspect "$v" >/dev/null; done
getent ahostsv4 www.heimanbo.com | awk '{print $1}' | grep -Fxq 47.253.252.143 || { echo "Set WWW A record to 47.253.252.143 first"; exit 1; }
docker exec heimanbo-test-caddy grep -Fq www.heimanbo.com /etc/caddy/Caddyfile || { echo "Add www to the live Caddyfile first"; exit 1; }
docker exec heimanbo-test-caddy caddy validate --config /etc/caddy/Caddyfile
docker pull "$BACK"
docker pull "$FRONT"
BCMD="$(docker image inspect "$BACK" -f '{{json .Config.Cmd}}')"
FCMD="$(docker image inspect "$FRONT" -f '{{json .Config.Cmd}}')"
[[ "$BCMD" == *uvicorn* && "$BCMD" == *8000* ]] || { echo "Wrong backend image"; exit 1; }
[ "$FCMD" = '["node","server.js"]' ] || { echo "Wrong frontend image"; exit 1; }
docker run --rm --entrypoint python "$BACK" -c '
from pathlib import Path
s=Path("/code/app/main.py").read_text()
assert """ "www.heimanbo.com": {"admin"} """.strip() not in s
b=s.split("def create_user(",1)[1].split("class UserActiveIn",1)[0]
assert "Merchant(" in b and "MerchantAccount(" in b
assert "\"admin\", \"producer\", \"merchant\"" in b
print("www multi-role and merchant creation code verified")
'
export COMPOSE_PROJECT_NAME="$(docker inspect heimanbo-v20-backend -f '{{index .Config.Labels "com.docker.compose.project"}}')"
FILES=(-f compose.yaml)
for f in compose.v21.override.yaml compose.v21.frontfix.yaml compose.v212.release.yaml compose.backend.recovery.yaml compose.backend.v212.yaml compose.navfix.yaml compose.merchant.final.yaml compose.backend.merchantfix2.yaml compose.merchantlocal.yaml compose.linksfix.yaml; do
  [ ! -f "$f" ] || FILES+=(-f "$f")
done
FILES+=(-f "$SRC/deploy/compose.www.override.yaml")
docker compose "${FILES[@]}" config --quiet
docker compose "${FILES[@]}" config --format json | python3 -c '
import sys,json
s=json.load(sys.stdin)["services"]
assert s["db"]["image"]=="postgres:16-alpine"
assert "heimanbo_v20_db" in str(s["db"]["volumes"])
assert "heimanbo_v20_videos" in str(s["backend"]["volumes"])
assert s["backend"]["image"].endswith("backend:v2.1.2-www1")
assert s["frontend"]["image"].endswith("frontend:v2.1.2-www1")
assert s["backend"]["environment"]["PUBLIC_APP_URL"]=="https://www.heimanbo.com"
print("Compose configuration verified")
'
docker compose "${FILES[@]}" up -d --no-deps --no-build --pull never --force-recreate backend frontend
HTTP=000
for n in $(seq 1 30); do
  HTTP="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 https://www.heimanbo.com/api/health || true)"
  [ "$HTTP" = 200 ] && break
  sleep 3
done
echo "www health HTTP $HTTP"
docker ps --filter name=heimanbo-v20-frontend --filter name=heimanbo-v20-backend
[ "$HTTP" = 200 ] || { docker logs --tail=60 heimanbo-v20-backend; exit 1; }
echo "WWW release online. Verify all role logins before retiring test host."
