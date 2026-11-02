#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
fail(){ echo "ERROR: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || fail "请使用 root 执行"
command -v docker >/dev/null || fail "Docker 未安装"
docker compose version >/dev/null || fail "Docker Compose 插件不可用"
[ -s .env ] || fail "缺少 .env，请先运行 deploy/generate-env.sh"
NETWORK="$(grep -E '^PROXY_NETWORK=' .env | tail -1 | cut -d= -f2-)"
NETWORK="${NETWORK:-heimanbo-test_app}"
docker network inspect "$NETWORK" >/dev/null 2>&1 || fail "找不到 Caddy 网络：$NETWORK"
CADDY="heimanbo-test-caddy"
docker inspect "$CADDY" >/dev/null 2>&1 || fail "找不到现有 Caddy 容器 $CADDY"
RUNNING="$(docker inspect -f '{{.State.Running}}' "$CADDY")"
[ "$RUNNING" = true ] || fail "现有 Caddy 未运行"
CADDY_NETWORKS="$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$CADDY")"
case " $CADDY_NETWORKS " in *" $NETWORK "*) ;; *) fail "Caddy 未加入网络 $NETWORK；当前：$CADDY_NETWORKS";; esac
docker compose config --quiet
echo "Compose 配置：OK"
echo "Caddy 容器：$CADDY"
echo "共享网络：$NETWORK"
echo "当前内存："
free -h
echo "当前磁盘："
df -h /
echo "镜像检查："
for image in \
  crpi-ik4qgw7vjkd1ccwd.cn-hangzhou.personal.cr.aliyuncs.com/heimanbo/backend:v2.0.0 \
  crpi-ik4qgw7vjkd1ccwd.cn-hangzhou.personal.cr.aliyuncs.com/heimanbo/frontend:v2.0.0; do
  if docker image inspect "$image" >/dev/null 2>&1; then
    echo "本地已有：$image"
  else
    echo "本地缺少：$image（安装阶段将尝试从 ACR 拉取）"
  fi
done
echo "DNS 检查（无解析会影响 HTTPS 签发）："
for d in auth work video merchant system api media; do
  if getent ahostsv4 "$d.heimanbo.com" >/dev/null 2>&1; then
    printf "%-28s " "$d.heimanbo.com"
    getent ahostsv4 "$d.heimanbo.com" | awk 'NR==1{print $1}'
  else
    echo "$d.heimanbo.com  未解析"
  fi
done
