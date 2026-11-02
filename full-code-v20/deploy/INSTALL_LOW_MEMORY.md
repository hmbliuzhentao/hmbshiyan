# V2.0 低内存服务器部署说明

## 重要边界
- 不启动第二个 Caddy；继续使用现有 `heimanbo-test-caddy`。
- V2.0 的 db/backend/frontend 加入现有 Caddy Docker 网络。
- PostgreSQL 使用独立命名卷 `heimanbo_v20_db`，视频使用 `heimanbo_v20_videos`。
- 不删除 V1.5 容器、镜像、网络或数据卷。
- 安装脚本在拉取镜像成功后才提示切换；输入 `SWITCH-V15` 后才停止 V1.5 的 frontend/backend/db。
- 若 V2.0 容器启动检查失败，脚本尝试重新启动原 V1.5 容器。
- 这不是完整备份；用户已选择跳过备份，数据丢失风险由此增加。

## 部署前必须完成
1. 在 Spaceship 将 `auth`、`work`、`video`、`merchant`、`system`、`api`、`media` 的 A 记录指向 `47.253.252.143`。
2. 把 `full-code-v20` 目录上传到 GitHub 仓库 `hmbliuzhentao/hmbshiyan` 的 `main` 分支（或独立分支），保留目录结构。
3. 在阿里云 ACR 为：
   - Context `/full-code-v20/backend` 构建 backend 标签 `v2.0.0`
   - Context `/full-code-v20/frontend` 构建 frontend 标签 `v2.0.0`
   两个构建必须成功后再继续。
4. 确认服务器现有 Caddy 容器名为 `heimanbo-test-caddy`，且已加入 `heimanbo-test_app` 网络；若名称或网络不同，先修改 `.env` 的 `PROXY_NETWORK` 和脚本中的容器名。
5. 确认现有 Caddyfile 路径和内容，保留现有站点配置。

## 服务器操作
将此目录上传并解压到 `/opt/heimanbo-v20`，然后：

```bash
cd /opt/heimanbo-v20
bash deploy/generate-env.sh
```

编辑 `.env` 中的 `ACME_EMAIL`。如无短信/SMTP/微信凭据，相关 OTP/OAuth 功能不会工作；账号密码登录仍可用。

运行只读预检：

```bash
bash deploy/preflight-v20.sh
```

预检通过后执行切换：

```bash
bash deploy/install-v20.sh
```

脚本会要求输入 `SWITCH-V15`。未输入不会停止旧容器。

## Caddy 切换
把 `deploy/Caddyfile.v20-snippet` 的站点块合并到现有 Caddyfile。不要复制第二个全局 options 块，也不要启动另一个 Caddy。先执行：

```bash
docker exec heimanbo-test-caddy caddy validate --config /etc/caddy/Caddyfile
```

通过后 reload：

```bash
docker exec heimanbo-test-caddy caddy reload --config /etc/caddy/Caddyfile
```

实际 Caddyfile 路径必须先从 `docker inspect` 的 Mounts 确认。若挂载的不是宿主机文件，需在宿主机修改其真实 Source 路径。

## 资源提示
当前 ECS 896MiB RAM。此 Compose 将 PostgreSQL / backend / frontend 内存上限分别设为 128MiB / 128MiB / 192MiB，总计 448MiB。属于低流量试运行参数；并发上传/播放、Next.js 内存峰值或数据库大查询可能触发 OOM。视频大文件不应长期保存在系统盘，建议后续接入 OSS。
