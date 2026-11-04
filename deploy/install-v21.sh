#!/usr/bin/env bash
# In-place V2.1.0 application rollout. Does not recreate PostgreSQL or touch named volumes.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
fail(){ echo "ERROR: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || fail "请使用 root 执行"
bash deploy/preflight-v21.sh

echo "拉取 V2.1.0 前后端镜像；不会拉取或重建数据库容器。"
docker compose pull backend frontend

echo "原位替换 backend / frontend。PostgreSQL 容器和现有命名卷保持不变。"
docker compose up -d --no-deps --force-recreate backend frontend

echo "等待后端健康检查……"
OK=0
for _ in $(seq 1 45); do
  if docker exec heimanbo-v20-backend python -c \
    "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3).read().decode())" >/tmp/heimanbo-v21-health.txt 2>&1; then OK=1; break; fi
  sleep 2
done
[ "$OK" = 1 ] || { cat /tmp/heimanbo-v21-health.txt || true; fail "后端健康检查失败；请查看 docker compose logs --tail=120 backend"; }
cat /tmp/heimanbo-v21-health.txt

echo "检查前端……"
docker exec heimanbo-v20-frontend sh -c 'wget -q -O /dev/null http://127.0.0.1:3000/' || fail "前端未响应"
echo "应用容器已升级为 V2.1.0。数据库未重建。"
docker compose ps

echo "最后确认 Caddy 的 test-v2.heimanbo.com 路由指向 heimanbo-v20-backend:8000 和 heimanbo-v20-frontend:3000。"
echo "按 deploy/Caddyfile.v21-snippet 修改现有 Caddyfile 后执行 validate 与 reload。"
