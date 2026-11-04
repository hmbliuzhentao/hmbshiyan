#!/usr/bin/env bash
# Publish only the provided release source to a new, non-force-pushed GitHub branch.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
REMOTE="https://github.com/hmbliuzhentao/hmbshiyan.git"
BRANCH="v2.1.2-deploy"
[ -f frontend/Dockerfile ] && [ -f backend/Dockerfile ] && [ -s frontend/public/brand-logo.png ] || {
  echo '源码或品牌 Logo 不完整，停止上传'; exit 1;
}
[ "$(cat VERSION | tr -d '\r\n')" = '2.1.2' ] || {
  echo '源码版本不为 2.1.2，停止上传'; exit 1;
}
[ -f .gitignore ] || { echo '缺少 .gitignore'; exit 1; }
# Prevent accidental push of personal configuration from the release directory.
if find . -name '*.pem' -o -name '*.key' -o -name '.env' | grep -q .; then
  echo '目录内有私钥或实际 .env：请先移出源码文件夹再上传'; exit 1;
fi
if [ ! -d .git ]; then git init -b "$BRANCH"; else git checkout -B "$BRANCH"; fi
if git remote get-url origin >/dev/null 2>&1; then
  [ "$(git remote get-url origin)" = "$REMOTE" ] || { echo 'origin 地址不是指定仓库，停止'; exit 1; }
else
  git remote add origin "$REMOTE"
fi
git add -A
# Refuse to publish any non-example environment or secret material.
if git diff --cached --name-only | grep -E '(^|/)(\.env($|\.)|[^/]+\.(pem|key|p12|pfx)$)' | grep -v -E '(^|/)\.env\.example$'; then
  echo '检测到敏感文件被暂存，停止提交'; exit 1
fi
if git diff --cached --quiet; then
  echo '没有待提交更改';
else
  git -c user.name='Heimanbo Deploy' -c user.email='deployment@users.noreply.github.com' commit -m 'Release Heimanbo V2.1.2 admin control center and delivery domains'
fi
echo '准备向 GitHub 推送新分支（不强制覆盖原分支）。如需认证，请使用 GitHub Token，而不是账号密码。'
git push --set-upstream origin "$BRANCH"
echo 'GitHub V2.1.2 源码已提交；请前往 ACR 构建 backend:v2.1.2 和 frontend:v2.1.2。'
