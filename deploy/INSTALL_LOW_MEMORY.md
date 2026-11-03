# V2.1.0 低内存服务器升级说明

本版本沿用现有美国 VPS、Docker、Caddy、PostgreSQL 容器和数据卷，不新建数据库，也不需要更换域名。

## 重要边界

- 继续使用现有 `heimanbo-test-caddy`，不启动第二个 Caddy。
- 保持 `heimanbo-v20-db`、`heimanbo_v20_db`、`heimanbo_v20_videos` 名称不变。
- 只替换 backend/frontend 镜像为 v2.1.0；数据库容器不重建。
- 后端启动会执行幂等的加列迁移和旧角色映射，不删除业务行或文件。
- 用户要求不做备份，本部署脚本不会创建数据库或视频卷备份；因此没有数据级回滚点。

## 部署前

1. 在本地电脑或 ACR 构建环境构建并推送 `heimanbo/backend:v2.1.0` 与 `heimanbo/frontend:v2.1.0`。不要在 896MiB 服务器本机编译 Next.js。
2. 将 `full-code-v21` 文件上传到现有部署目录。
3. 保留服务器现有 `.env`，只追加：
   - `PUBLIC_APP_URL=https://test-v2.heimanbo.com`
   - `SITE_ORIGIN=https://test-v2.heimanbo.com`
   - `WECHAT_REDIRECT_URI=https://test-v2.heimanbo.com/api/auth/wechat/callback`
4. 不要重新生成 POSTGRES_PASSWORD、JWT_SECRET、ADMIN_PASSWORD，不要改数据库名/用户/卷名。
5. 确认 `test-v2.heimanbo.com` A 记录指向美国 VPS，TCP 80/443 已开放，Caddy 已连接 `PROXY_NETWORK`。

## 服务器执行

```bash
bash deploy/preflight-v21.sh
bash deploy/install-v21.sh
```

脚本不会停止或重建数据库容器。后端和前端原位重建，等待健康检查。

## Caddy

把 `deploy/Caddyfile.v21-snippet` 合并到现有 Caddyfile，替换旧 `test-v2.heimanbo.com` 块；先 validate 再 reload。不要重复添加同一 host，也不要启动第二个 Caddy。

## 低内存提醒

Compose 对 Postgres / backend / frontend 分别设置 128MiB / 128MiB / 192MiB 内存上限。属于低流量试运行参数；大文件上传/播放和并发请求可能触发 OOM。后续建议至少 2GB RAM，并将视频文件迁移至 OSS/S3。
