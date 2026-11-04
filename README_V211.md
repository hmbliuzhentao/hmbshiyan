# 黑曼波 VideoHub V2.1.1 - 导航精简与商家后台开户

## 修改内容

- 管理员侧边栏简化为两组，共 7 个简短入口。取消冗余字符图标，上传视频、上传记录可在“视频管理”中操作。
- 管理员可以在“商家管理”直接创建商家账号，或在“账号管理”选择“商家”角色开户。
- 后端 `POST /api/users` 仅允许已登录的管理员创建三种角色。商家开户时，在单个数据库事务中建立 `users`、`merchants`、`merchant_accounts` 关联。无需人工审核；不影响其他商家的订单和视频访问权限。
- 保留微信自主注册，不重新开放公开的邮箱密码注册。后台创建的商家可使用管理员提供的邮箱/初始密码登录并随后绑定微信。

## 低内存阿里云部署注意

现有实例为阿里云美国 VPS + 宝塔 + Docker + 阿里云 ACR，源项目 `/opt/heimanbo-v20`，共享 Caddy 网络 `heimanbo-test_app`。

1. 将本项目推送到 GitHub 独立分支 `v2.1.1-deploy`。不需要重置已有的 `v2.1.0-deploy`。
2. 在 ACR 从这一分支分别构建 `backend:v2.1.1`、`frontend:v2.1.1`：后端构建上下文 `/backend`，Dockerfile `Dockerfile`；前端 `/frontend`，Dockerfile `Dockerfile`。
3. 在 VPS 拉取两个 v2.1.1 镜像，确认前端 `docker image inspect` 显示 `Cmd=["node","server.js"]`，而不是 `uvicorn`。
4. 更新原有 Compose 的 backend、frontend 镜像引用，**保留原数据库服务、原 .env、原持久化卷、原 Caddy**；前端网络必须与 Caddy 共享 `heimanbo-test_app`。不执行 `down -v`、卷清理或数据库重建。
5. 只重新创建 backend/frontend 服务后，测试 HTTP 200、管理员创建商家、商家账号登录、仅显示自己订单。

本包不包含运行中的数据库或 SSH/ACR 凭据，不代表已经在线上部署。
