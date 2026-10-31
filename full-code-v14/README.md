# VideoHub · 视频数据工作台 MVP

一个独立可部署的演示项目：Next.js 15 + FastAPI + PostgreSQL + Caddy。

> 这是原创的同类型产品最小实现，不是 video.vfxcn.cn 的源代码或登录后界面的复刻。

## 已实现

- 管理员与普通用户登录（HttpOnly、SameSite Cookie，密码 Argon2 哈希）
- 首次启动自动建立管理员账户（只在不存在时创建）
- PostgreSQL 数据库和基础表
- 视频上传（MP4/MOV/WebM；100 MB 上限；文件签名初检）
- 需要登录的视频播放接口、文件名搜索和分页
- 删除视频（管理员或上传者）
- 数据看板（数量、占用空间、今日新增、七日新增）
- 上传历史任务记录（不是异步转码队列）
- 管理员创建普通用户或管理员
- Docker Compose + Caddy 反向代理

## 运行要求

- Ubuntu 22.04/24.04 或其他可运行 Docker Engine 的 Linux
- Docker Engine / Docker Compose v2
- 2 vCPU、4 GB RAM、40 GB SSD 推荐起步；视频多时应接对象存储

## 本地或服务器 HTTP 验证

```bash
cp .env.example .env
# 修改 .env 中 POSTGRES_PASSWORD、JWT_SECRET、ADMIN_EMAIL、ADMIN_PASSWORD
# 生成密码或随机密钥：python3 -c 'import secrets; print(secrets.token_urlsafe(40))'
docker compose up -d --build
docker compose ps
curl http://localhost:8080/api/health
```

访问：`http://localhost:8080`。使用 `.env` 中的管理员邮箱/密码登录。

## 配置正式域名和 HTTPS

1. 给子域名添加 A 记录指向服务器公网 IP，例：`video.example.com`。
2. 确保 80、443 端口对外开放，且未被其他进程占用。
3. 修改 `.env`：

```ini
SITE_DOMAIN=video.example.com
SITE_ORIGIN=https://video.example.com
HTTP_PORT=80
HTTPS_PORT=443
COOKIE_SECURE=true
```

4. 运行：`docker compose up -d --build`
5. 打开 `https://video.example.com`。

Caddy 根据有效域名、DNS 和 80/443 开放情况自动申请/续期 HTTPS 证书。
**域名 `example.com` 只是占位符，必须换成你自己的域名。**

如果使用中国大陆服务器，需按适用政策处理备案及相关资质。

## 常见维护操作

```bash
# 看日志
docker compose logs -f --tail=100
# 检查运行状态
docker compose ps
# 数据库备份（保存在宿主机当前目录）
docker compose exec -T db pg_dump -U videohub -d videohub > videohub.sql
# 更新代码后重新构建
docker compose up -d --build
# 停止容器（不删除数据卷）
docker compose down
```

数据库备份命令里的数据库名和用户名需与 `.env` 对应。数据库备份**不包含视频文件**，必须单独备份 Docker 的 `video_data` 卷、Caddy 证书卷和 `.env`，并定期做恢复演练。不要执行 `docker compose down -v`，除非你明确要删除全部数据。

## API 清单

| 方法 | 地址 | 功能 | 权限 |
| --- | --- | --- | --- |
| GET | /api/health | 健康检查 | 公开 |
| POST | /api/auth/login | 登录 | 公开 |
| POST | /api/auth/logout | 退出 | 已登录 |
| GET | /api/auth/me | 当前用户 | 已登录 |
| GET | /api/dashboard | 统计看板 | 已登录 |
| GET | /api/videos?q=&page= | 视频列表 | 已登录 |
| POST | /api/videos | 表单字段 file 上传 | 已登录 |
| GET | /api/videos/{id}/stream | 在线预览 | 已登录 |
| DELETE | /api/videos/{id} | 删除视频 | 管理员/上传者 |
| GET | /api/tasks | 最近任务记录 | 已登录 |
| GET | /api/users | 用户列表 | 管理员 |
| POST | /api/users | 创建用户 | 管理员 |

## 数据库模型

- `users`: 用户信息和密码哈希
- `videos`: 视频名称、对象路径、大小、创建者、状态
- `tasks`: 上传记录及关联视频（删除视频后保留历史）

## 文件结构

```text
videohub-starter/
├── .env.example
├── compose.yaml
├── deploy/Caddyfile
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/main.py
└── frontend/
    ├── Dockerfile
    ├── package.json
    └── app/
        ├── layout.tsx
        ├── page.tsx
        └── globals.css
```

## V1 的边界与正式商用前须补齐的事项

- **暂未实现**：TikTok 接口、音视频转码、封面生成、真实播放量、自动任务重试、批量导出、短信验证、多租户。
- 目前任务中心只有完成的上传记录；不具备 Redis/Celery 异步队列。
- 采用本地挂载卷保存视频；单文件 100 MB，不支持断点续传或超大文件。生产应采用对象存储直传与签名 URL。
- 简化的数据库建表方式 `create_all` 只适合初版测试；生产需 Alembic 迁移。
- 生产须增加操作审计、登录速率限制、账户冻结或 MFA、权限审查、数据保留规则、内容扫描、异地备份与监控告警。
- 日常运维需要补充依赖安全更新、镜像漏洞扫描、存储容量告警。若配置使用 PostgreSQL 密码包含 URL 特殊字符，需 URL 编码或改用单独变量构造连接字符串。
- 此项目附有源代码，但尚未在你的服务器上构建及通过端到端测试；请先在测试环境验收再用于实际业务。
