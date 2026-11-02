# V2.0 域名与面板架构

所有子域名先创建独立 A 记录，指向当前规划服务器 `47.253.252.143`。如果服务器公网 IP 已变更，DNS 以实际 ECS 公网 IP 为准。

| 子域名 | 用途 | 允许角色 |
|---|---|---|
| heimanbo.com / www.heimanbo.com | 品牌入口，跳转统一登录 | 全部 |
| auth.heimanbo.com | 统一登录、注册、找回密码、微信授权回调 | 未登录用户及全部账号 |
| work.heimanbo.com | 内部运营管理 | super_admin / admin / manager / viewer |
| video.heimanbo.com | 视频制作中心 | super_admin / admin / manager / producer / editor / viewer |
| merchant.heimanbo.com | 商家审核工作台 | merchant |
| system.heimanbo.com | 系统管理 | super_admin / admin |
| api.heimanbo.com | 后端 API 集成入口 | 由每个 API 自身权限控制 |
| media.heimanbo.com | 受保护媒体接口入口 | 由后端资源归属校验 |
| test-v2.heimanbo.com | V2.0 测试入口（可选） | 仅测试阶段开放 |

所有域名共用一套 Next.js、FastAPI 和 PostgreSQL。面板分域名，不代表拆成多套数据库。登录 Cookie 设置为 `.heimanbo.com`，实现子域名间统一会话；SameSite=Lax、Secure、HttpOnly。

## DNS
添加 DNS 记录：
- 根域名 Host: `@`，类型 A
- Host: `www`，类型 CNAME 指向根域名（或 A 指向同一 IP）
- 子域名 Host: `auth` / `work` / `video` / `merchant` / `system` / `test-v2` / `api` / `media`，类型 A
- Value: `47.253.252.143`
- TTL: Auto

不建议初期使用通配符 DNS 或通配符证书。Caddy 会为 Caddyfile 中列出的域名单独申请 HTTPS 证书。

## 安全
- 商家域名只允许 merchant 角色；系统域名只允许 admin / super_admin。
- API 域名不代表免鉴权，业务 API 仍逐路由检查角色与 merchant_id。
- 媒体文件必须经过订单/任务/商家归属验证，不允许公开目录。
