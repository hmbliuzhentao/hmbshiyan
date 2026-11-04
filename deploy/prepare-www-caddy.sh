#!/usr/bin/env bash
# Enable www.heimanbo.com on existing Caddy site, retaining test-v2.
# No PostgreSQL, videos, app image or Docker volume changes.
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo "请使用 root"; exit 1; }
CADDY=heimanbo-test-caddy
docker inspect "$CADDY" >/dev/null
if ! getent ahostsv4 www.heimanbo.com | awk '{print $1}' | grep -Fxq 47.253.252.143; then
  echo "www DNS 尚未解析到 47.253.252.143，先设置 A 记录再执行"
  exit 1
fi
FILE="$(docker inspect "$CADDY" --format '{{range .Mounts}}{{if eq .Destination "/etc/caddy/Caddyfile"}}{{.Source}}{{end}}{{end}}')"
if [ -z "$FILE" ]; then
  DIR="$(docker inspect "$CADDY" --format '{{range .Mounts}}{{if eq .Destination "/etc/caddy"}}{{.Source}}{{end}}{{end}}')"
  if [ -n "$DIR" ]; then FILE="$DIR/Caddyfile"; fi
fi
[ -n "$FILE" ] && [ -f "$FILE" ] || {
  echo "无法确定正在挂载的 Caddyfile，已停止；请先查看 Docker 挂载"
  docker inspect "$CADDY" --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
  exit 1
}
if grep -Fq 'test-v2.heimanbo.com, www.heimanbo.com {' "$FILE"; then
  echo "www 已写入现有站点配置"
  docker exec "$CADDY" caddy validate --config /etc/caddy/Caddyfile
  exit 0
fi
if grep -Fq 'www.heimanbo.com' "$FILE"; then
  echo "www 已在其他 Caddy 配置中出现；停止，避免覆盖已有网站"
  exit 1
fi
grep -Fq 'test-v2.heimanbo.com {' "$FILE" || {
  echo "未发现预期的 test-v2 站点，停止"
  exit 1
}
SAVE="$FILE.before-www"
[ ! -e "$SAVE" ] || { echo "已有 $SAVE，先检查原备份，停止"; exit 1; }
cp -p "$FILE" "$SAVE"
python3 - "$FILE" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
old="test-v2.heimanbo.com {"
content=p.read_text()
assert content.count(old)==1
p.write_text(content.replace(old,"test-v2.heimanbo.com, www.heimanbo.com {",1))
PY
if ! docker exec "$CADDY" caddy validate --config /etc/caddy/Caddyfile; then
  cp -p "$SAVE" "$FILE"
  echo "配置校验失败，已恢复原文件，未热重载"
  exit 1
fi
if ! docker exec "$CADDY" caddy reload --config /etc/caddy/Caddyfile; then
  cp -p "$SAVE" "$FILE"
  docker exec "$CADDY" caddy reload --config /etc/caddy/Caddyfile || true
  echo "热重载失败，已恢复旧配置文件"
  exit 1
fi
echo "Caddy 已启用 www，旧 test-v2 保留；请确认 HTTPS 正常再切换应用镜像"
curl -sS -o /dev/null -w 'www HTTPS: %{http_code}\n' --max-time 20 https://www.heimanbo.com/ || true
