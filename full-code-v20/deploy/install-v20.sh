#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
fail(){ echo "ERROR: $*" >&2; exit 1; }
bash deploy/preflight-v20.sh
echo
echo "将先拉取 V2.0 镜像。若镜像不存在或 ACR 无权限，将停止，不会停止 V1.5。"
docker compose pull db backend frontend

echo
echo "即将执行短暂停机切换：只停止 V1.5 的 frontend/backend/db，保留现有 Caddy。"
echo "不会删除旧容器、镜像、网络或数据卷。"
read -r -p "输入 SWITCH-V15 确认继续：" CONFIRM
[ "$CONFIRM" = "SWITCH-V15" ] || fail "用户未确认，未停止旧服务"

OLD=(heimanbo-test-frontend heimanbo-test-backend heimanbo-test-db)
OLD_RUNNING=()
for c in "${OLD[@]}"; do
  if docker inspect "$c" >/dev/null 2>&1 && [ "$(docker inspect -f '{{.State.Running}}' "$c")" = true ]; then
    OLD_RUNNING+=("$c")
  fi
done

rollback(){
  echo "V2.0 启动失败，尝试重新启动原 V1.5 容器……" >&2
  docker compose stop frontend backend db >/dev/null 2>&1 || true
  for c in "${OLD_RUNNING[@]}"; do docker start "$c" >/dev/null 2>&1 || true; done
}
trap 'rollback' ERR

for c in "${OLD_RUNNING[@]}"; do docker stop "$c"; done
docker compose up -d db backend frontend

echo "等待数据库健康……"
for i in $(seq 1 60); do
  status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' heimanbo-v20-db 2>/dev/null || true)"
  [ "$status" = healthy ] && break
  sleep 2
done
[ "$(docker inspect -f '{{.State.Health.Status}}' heimanbo-v20-db)" = healthy ]

echo "检查后端健康接口……"
for i in $(seq 1 30); do
  if docker exec heimanbo-v20-backend python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)" \
    >/dev/null 2>&1; then break; fi
  sleep 2
done
docker exec heimanbo-v20-backend python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3).read().decode())"

echo "检查前端响应……"
docker exec heimanbo-v20-frontend sh -c \
  'wget -q -O /dev/null http://127.0.0.1:3000/'

trap - ERR
echo
echo "V2.0 容器已启动。现有 Caddy 尚未切换到 V2.0。"
echo "下一步：把 deploy/Caddyfile.v20-snippet 合并进现有 Caddyfile，验证并 reload。"
docker compose ps
