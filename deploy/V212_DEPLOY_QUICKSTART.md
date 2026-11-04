# 黑曼波 V2.1.2 · 阿里云 ECS / 宝塔 / ACR 原位升级

**目标：** 不创建数据库备份（按用户要求），不删除任何数据卷；只更新前后端容器；原 Caddy / HTTPS 继续运行。

## A. GitHub

在宝塔文件管理上传并解压本 ZIP，最终项目源码目录为 `/www/server/heimanbo2.1.2-deploy-ready`（可按解压出的实际目录调整）。

```bash
cd /www/server/heimanbo2.1.2-deploy-ready
bash deploy/push-github-v212.sh
```

预期 GitHub 新分支：`hmbliuzhentao/hmbshiyan` → `v2.1.2-deploy`。不要用旧分支代替。

## B. 阿里云 ACR 云端构建两个独立镜像

- `heimanbo/backend`：Branch `v2.1.2-deploy`，构建上下文 `/backend`，Dockerfile 文件名 `Dockerfile`，镜像版本 `v2.1.2`。
- `heimanbo/frontend`：Branch `v2.1.2-deploy`，构建上下文 `/frontend`，Dockerfile 文件名 `Dockerfile`，镜像版本 `v2.1.2`。

**必须分别检查两个镜像构建日志**，前端应该基于 `node:22-alpine`，不能再次构建出 `uvicorn` 后端镜像。不要把宝塔 `/www/server/...` 路径填进 ACR 构建规则。

## C. 新镜像显示构建成功后，宝塔 root 执行

```bash
cd /www/server/heimanbo2.1.2-deploy-ready
bash deploy/upgrade-from-v210-to-v212.sh
```

仅改前后端 Compose 覆盖文件并重建应用容器。现有 `.env`、PostgreSQL 容器、Caddy、原视频数据卷均保持不变。微信 AppID/Secret 尚未取得前不启动真实微信登录。

## D. 业务验收

先用 `https://test-v2.heimanbo.com` 检查后台菜单、商家后台创建账号、三个角色权限及订单关联视频隔离。新域名 DNS/Caddy 以后再切换，不能在 DNS 未生效时贸然修改 Caddy。
