# V2.1.0 镜像构建与发布

低内存 VPS 不建议在服务器本机执行 `docker build`。请在有 Docker 的本地电脑或阿里云 ACR 构建环境中完成构建，并推送到当前 V2.0 使用的同一 ACR 仓库。

镜像地址：

- `crpi-ik4qgw7vjkd1ccwd.cn-hangzhou.personal.cr.aliyuncs.com/heimanbo/backend:v2.1.0`
- `crpi-ik4qgw7vjkd1ccwd.cn-hangzhou.personal.cr.aliyuncs.com/heimanbo/frontend:v2.1.0`

在项目根目录执行（需先完成 ACR 登录）：

```bash
docker build -t crpi-ik4qgw7vjkd1ccwd.cn-hangzhou.personal.cr.aliyuncs.com/heimanbo/backend:v2.1.0 ./backend
docker build -t crpi-ik4qgw7vjkd1ccwd.cn-hangzhou.personal.cr.aliyuncs.com/heimanbo/frontend:v2.1.0 ./frontend
docker push crpi-ik4qgw7vjkd1ccwd.cn-hangzhou.personal.cr.aliyuncs.com/heimanbo/backend:v2.1.0
docker push crpi-ik4qgw7vjkd1ccwd.cn-hangzhou.personal.cr.aliyuncs.com/heimanbo/frontend:v2.1.0
```

推送后在美国 VPS 的现有项目目录中放入 V2.1.0 项目文件，保留原 `.env`，只追加或确认以下配置：

```dotenv
PUBLIC_APP_URL=https://test-v2.heimanbo.com
SITE_ORIGIN=https://test-v2.heimanbo.com
WECHAT_REDIRECT_URI=https://test-v2.heimanbo.com/api/auth/wechat/callback
```

不要重新生成 `POSTGRES_PASSWORD`、`JWT_SECRET` 或 `ADMIN_PASSWORD`，不要修改现有 PostgreSQL volume 名称。

```bash
bash deploy/install-v21.sh
```

然后按 `Caddyfile.v21-snippet` 更新现有 Caddy 中 `test-v2.heimanbo.com` 站点块，先 validate 再 reload。脚本不会备份数据库，也不会重建数据库容器或删除数据卷。
