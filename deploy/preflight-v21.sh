#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
fail(){ echo "ERROR: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || fail "请使用 root 执行"
command -v docker >/dev/null || fail "Docker 未安装"
docker compose version >/dev/null || fail "Docker Compose 插件不可用"
[ -s .env ] || fail "缺少现有 .env；请把 V2.1.0 需要的 PUBLIC_APP_URL / WECHAT_REDIRECT_URI 追加进去，不要重新生成数据库密码或 JWT_SECRET"
NETWORK="$(grep -E '^PROXY_NETWORK=' .env | tail -1 | cut -d= -f2-)"
NETWORK="${NETWORK:-heimanbo-test_app}"
docker network inspect "$NETWORK" >/dev/null 2>&1 || fail "找不到 Caddy 网络：$NETWORK"
CADDY="heimanbo-test-caddy"
docker inspect "$CADDY" >/dev/null 2>&1 || fail "找不到现有 Caddy 容器 $CADDY"
[ "$(docker inspect -f '{{.State.Running}}' "$CADDY")" = true ] || fail "现有 Caddy 未运行"
DB="heimanbo-v20-db"
docker inspect "$DB" >/dev/null 2>&1 || fail "找不到现有 PostgreSQL 容器 $DB"
[ "$(docker inspect -f '{{.State.Running}}' "$DB")" = true ] || fail "现有 PostgreSQL 未运行；停止升级，先检查数据库"
DB_HEALTH="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$DB")"
case "$DB_HEALTH" in healthy|no-healthcheck) ;; *) fail "PostgreSQL 健康状态为 $DB_HEALTH；停止升级";; esac
CADDY_NETWORKS="$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$CADDY")"
case " $CADDY_NETWORKS " in *" $NETWORK "*) ;; *) fail "Caddy 未加入网络 $NETWORK；当前：$CADDY_NETWORKS";; esac
docker compose config --quiet
echo "Compose 配置：OK"
echo "Caddy 容器：$CADDY"
echo "PostgreSQL 容器：$DB（$DB_HEALTH）"
echo "共享网络：$NETWORK"
echo "当前内存："; free -h
echo "当前磁盘："; df -h /
echo "V2.1.0 镜像检查："
for image in \
  crpi-ik4qgw7vjkd1ccwd.cn-hangzhou.personal.cr.aliyuncs.com/heimanbo/backend:v2.1.0 \
  crpi-ik4qgw7vjkd1ccwd.cn-hangzhou.personal.cr.aliyuncs.com/heimanbo/frontend:v2.1.0; do
  if docker image inspect "$image" >/dev/null 2>&1; then echo "本地已有：$image"; else echo "尚未拉取：$image"; fi
done
echo "DNS 检查："
getent ahostsv4 test-v2.heimanbo.com | awk 'NR==1{print "test-v2.heimanbo.com -> "$1}' || fail "test-v2.heimanbo.com 未解析"
echo "当前容器："
docker compose ps || true
echo "预检通过。该脚本没有停止容器、修改数据卷或运行数据库迁移。"
