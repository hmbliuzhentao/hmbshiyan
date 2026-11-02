# V2.0 ACR 与服务器部署

## ACR
沿用杭州地域个人版，不覆盖 V1.5 的 `v1.5` 标签：
- 后端仓库：`heimanbo/backend`
- Branch：`main`
- Context：`/full-code-v20/backend`
- Dockerfile：`Dockerfile`
- Tag：`v2.0.0`
- 海外构建：开启

- 前端仓库：`heimanbo/frontend`
- Branch：`main`
- Context：`/full-code-v20/frontend`
- Dockerfile：`Dockerfile`
- Tag：`v2.0.0`
- 海外构建：开启

构建前必须把原始 Logo PNG 放到 V2.0 frontend/public；缺失时构建会按预期失败。

## 服务器
1. 不要覆盖 `/opt/heimanbo` 或 `/opt/heimanbo-test`。
2. 创建 `/opt/heimanbo-v20`，上传 `compose.yaml`、`.env`、`deploy/Caddyfile`。
3. `.env` 从 `.env.example` 复制，所有随机密钥重新生成；不要把真实 `.env` 提交 GitHub。
4. 先确认所有子域名 DNS 指向实际服务器 IP，安全组开放 TCP 80/443。
5. 先执行 `docker compose config --quiet`，再拉取镜像。
6. V1.5 与 V2.0 不可在当前 896MiB RAM 主机上同时启动。先用新服务器或扩容到至少 2GB RAM（推荐 4GB）完成并行验收；否则安排停机切换和回滚窗口。
7. 正式切换前备份数据库、视频卷、商家素材卷、`.env` 与 Caddy data。
8. 仅在数据迁移、商家隔离、审核交付、登录与证书验收通过后切换正式域名。

当前 Compose 使用独立命名卷 `heimanbo_v20_*`，不会复用 V1.5 数据卷。
