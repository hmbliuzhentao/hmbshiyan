# V2.1.0 低内存美国 VPS 原位部署

## 部署结构

- 公开站点：`https://test-v2.heimanbo.com`
- 美国 VPS：继续使用现有 Docker 与 Caddy。
- PostgreSQL 容器：`heimanbo-v20-db`（不重建）。
- 数据卷：`heimanbo_v20_db`、`heimanbo_v20_videos`（保持原名）。
- 后端/前端容器名与 Caddy 网络别名保持 `heimanbo-v20-backend`、`heimanbo-v20-frontend`，仅镜像升级到 `v2.1.0`。

## 1. 构建并推送 ACR 镜像

按 `deploy/BUILD_AND_PUSH_V21.md` 在本地 Docker 或 ACR 构建环境构建、推送：

- `heimanbo/backend:v2.1.0`
- `heimanbo/frontend:v2.1.0`

低内存 VPS 不建议本机编译 Next.js。

## 2. 上传代码与保留现有环境变量

将 `full-code-v21` 内容上传到现有部署目录。**保留现有 `.env`**，只追加/确认：

```dotenv
PUBLIC_APP_URL=https://test-v2.heimanbo.com
SITE_ORIGIN=https://test-v2.heimanbo.com
WECHAT_REDIRECT_URI=https://test-v2.heimanbo.com/api/auth/wechat/callback
DELETE_MEDIA_AFTER_MERCHANT_CONFIRMATION=true
```

不要重新生成数据库密码、JWT_SECRET 或 ADMIN_PASSWORD。

## 3. 预检和应用升级

```bash
bash deploy/preflight-v21.sh
bash deploy/install-v21.sh
```

升级脚本只拉取并重建 backend/frontend，不会重建 db、不执行 down -v、不删除数据卷。后端启动时执行 V2.1 幂等迁移。

## 4. Caddy 切换

将 `deploy/Caddyfile.v21-snippet` 的 `test-v2.heimanbo.com` 站点块合并到现有 Caddyfile，替换旧站点块，不能出现两个相同 host 的重复块。确认现有 Caddy 与 V2.1 容器在同一 Docker 网络。

```bash
docker exec heimanbo-test-caddy caddy validate --config /etc/caddy/Caddyfile
docker exec heimanbo-test-caddy caddy reload --config /etc/caddy/Caddyfile
```

实际 Caddyfile 路径需从 `docker inspect` Mounts 确认。

## 5. 验收

- `https://test-v2.heimanbo.com/api/health` 返回 `{"ok":true}`。
- 登录页显示三种角色的说明；微信按钮仅在 AppID/AppSecret 配置后启用。
- 管理员能分配任务；拍摄剪辑只能看分配给自己的任务并接单；商家 A 无法查看商家 B 的订单/视频。
- 商家上传需求 → 管理员报价转单 → 商家发布视频任务 → 管理员分配 → 拍摄剪辑接单/上传 → 商家审核/退回 → 拍摄剪辑替换新版 → 商家通过。
