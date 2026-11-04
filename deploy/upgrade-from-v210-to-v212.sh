#!/usr/bin/env bash
# Safe(ish) V2.1.2 app-only rollout from the original Compose project.
# Does NOT create a database backup (per owner request) and does NOT touch or recreate volumes.
# Run only AFTER both ACR images have built successfully.
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo '请使用 root 执行'; exit 1; }
DST='/opt/heimanbo-v20'
REG='crpi-ik4qgw7vjkd1ccwd.cn-hangzhou.personal.cr.aliyuncs.com/heimanbo'
cd "$DST"
[ -s .env ] || { echo '原网站 .env 未找到：停止升级'; exit 1; }
[ -s compose.yaml ] || { echo '原网站 compose.yaml 未找到：停止升级'; exit 1; }
docker inspect heimanbo-v20-db heimanbo-v20-backend heimanbo-v20-frontend heimanbo-test-caddy >/dev/null
for v in heimanbo_v20_db heimanbo_v20_videos; do
  docker volume inspect "$v" >/dev/null || { echo "原数据卷 $v 缺失，停止"; exit 1; }
done
PROJECT="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' heimanbo-v20-backend)"
[ -n "$PROJECT" ] && [ "$PROJECT" != '<no value>' ] || { echo '无法获取原 Compose 项目名'; exit 1; }
export COMPOSE_PROJECT_NAME="$PROJECT"
# Only replace application image references; intentionally preserve old .env, db, Caddy, volumes.
echo '===== 拉取 V2.1.2 镜像 ====='
docker pull "$REG/backend:v2.1.2"
docker pull "$REG/frontend:v2.1.2"
CMD="$(docker image inspect -f '{{json .Config.Cmd}}' "$REG/frontend:v2.1.2")"
[ "$CMD" = '["node","server.js"]' ] || { echo "前端镜像错误: CMD=$CMD，不升级"; exit 1; }
FPORT="$(docker image inspect -f '{{json .Config.ExposedPorts}}' "$REG/frontend:v2.1.2")"
echo "$FPORT" | grep -Fq '3000/tcp' || { echo '前端镜像未暴露 3000/tcp，停止'; exit 1; }
NET='heimanbo-test_app'
docker network inspect "$NET" >/dev/null
if ! docker inspect heimanbo-test-caddy --format '{{range $name,$v := .NetworkSettings.Networks}}{{println $name}}{{end}}' | grep -Fxq "$NET"; then
 echo 'Caddy 不在共享网络，停止升级'; exit 1
fi
cat > compose.v212.release.yaml <<EOF
services:
  backend:
    image: $REG/backend:v2.1.2
    networks:
      edge:
        aliases:
          - heimanbo-v20-backend
  frontend:
    image: $REG/frontend:v2.1.2
    networks:
      edge:
        aliases:
          - heimanbo-v20-frontend
networks:
  edge:
    name: $NET
    external: true
EOF
# Keep existing overlays from previous patches, then put V2.1.2 LAST so its images win.
COMPOSE_ARGS=(-f compose.yaml)
for existing in compose.v21.override.yaml compose.v21.frontfix.yaml; do
  if [ -f "$existing" ]; then COMPOSE_ARGS+=(-f "$existing"); fi
done
COMPOSE_ARGS+=(-f compose.v212.release.yaml)
docker compose "${COMPOSE_ARGS[@]}" config --quiet
# Verify rendering before any state change; only app images can change.
docker compose "${COMPOSE_ARGS[@]}" config --format json | python3 -c '
import sys,json
x=json.load(sys.stdin)
s=x["services"]
assert set(s)>= {"db","backend","frontend"},"Missing service"
assert s["db"]["image"]=="postgres:16-alpine", "DB image unexpected"
assert s["backend"]["image"].endswith("/backend:v2.1.2")
assert s["frontend"]["image"].endswith("/frontend:v2.1.2")
assert any("heimanbo_v20_db" in str(i) for i in s["db"].get("volumes",[])),"Database volume changed"
assert any("heimanbo_v20_videos" in str(i) for i in s["backend"].get("volumes",[])),"Video volume changed"
assert "edge" in s["frontend"]["networks"],"Missing Caddy edge network"
assert "edge" in s["backend"]["networks"],"Missing Caddy edge network"
print("CHECK OK: DB/video volume names, app images, networks")
'
echo '===== 仅更新前后端容器；不更新数据库或 Caddy ====='
docker compose "${COMPOSE_ARGS[@]}" up -d --no-deps --no-build --pull never --force-recreate backend frontend
# Wait for Next.js to boot. Avoid testing the HTTPS proxy immediately after container creation.
OK=0
for i in $(seq 1 30); do
  status="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 https://test-v2.heimanbo.com/ || true)"
  if [ "$status" = 200 ] || [ "$status" = 302 ] || [ "$status" = 307 ]; then OK=1; break; fi
  sleep 3
done
printf 'SITE_HTTP=%s\n' "${status:-unavailable}"
docker ps --filter name=heimanbo-v20-frontend --filter name=heimanbo-v20-backend
if [ "$OK" -ne 1 ]; then
  echo '新站尚未正常响应。查看 Caddy 及前端日志，勿触碰数据库：'
  docker logs --tail=40 heimanbo-v20-frontend || true
  docker logs --tail=20 heimanbo-test-caddy || true
  exit 1
fi
echo 'V2.1.2 应用容器已切换，接下来进行功能验收。微信登录需审核通过并配置 AppID/Secret 后才可用。'
