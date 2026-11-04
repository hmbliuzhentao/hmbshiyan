#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -e .env ]; then
  echo "已有 .env，为避免覆盖，停止。"
  exit 1
fi
command -v openssl >/dev/null
cp .env.example .env
DB_PASS="$(openssl rand -hex 32)"
JWT="$(openssl rand -hex 48)"
ADMIN_PASS="$(openssl rand -hex 18)"
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${DB_PASS}|" .env
sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${JWT}|" .env
sed -i "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=${ADMIN_PASS}|" .env
cat > /root/heimanbo-v21-admin-credentials.txt <<EOF
BlackMambo V2.1.0 initial admin
Email: admin@heimanbo.com
Password: ${ADMIN_PASS}
Generated: $(date -Is)
Change this password immediately after first login.
EOF
chmod 600 .env /root/heimanbo-v21-admin-credentials.txt
echo "已生成独立数据库密码、JWT 密钥和管理员密码。"
echo "管理员凭据保存在 /root/heimanbo-v21-admin-credentials.txt（权限 600）。"
echo "请编辑 .env 中的 ACME_EMAIL，并在需要时配置 SMTP、短信和微信服务。"
