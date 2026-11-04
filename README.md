# 黑曼波工作台 V2.1.0

本版本以 `https://test-v2.heimanbo.com` 为主站，统一为三个角色：管理员、拍摄剪辑、商家。

## 业务闭环

商家发布需求/订单 → 管理员报价与转单 → 商家发布制作任务 → 管理员分配拍摄剪辑 → 拍摄剪辑接单制作并上传 → 商家预览审核/退回 → 拍摄剪辑提交新版 → 商家通过并登记发布。

## 角色

- 管理员：全站权限。
- 拍摄剪辑：只看管理员分配给自己的任务，接单后上传制作视频。
- 商家：只能看自己发布的订单和关联的全部制作视频，其他商家数据严格隔离。

商家与拍摄剪辑通过微信网站扫码授权自主注册，无需人工审核；管理员只能由后台创建。微信开放平台尚未申请时，代码已预留授权回调与安全状态校验，待配置 AppID/AppSecret 后启用。

## 部署

请先阅读 `docs/DEPLOYMENT.md`、`docs/DATA_MIGRATION.md` 和 `deploy/BUILD_AND_PUSH_V21.md`。V2.1.0 沿用原 PostgreSQL 与视频卷，不重建数据库容器。用户选择不做备份，部署脚本不创建备份。

## 项目目录

- `backend/` FastAPI 后端、角色/租户权限、微信 OAuth、任务分配与审核。
- `frontend/` Next.js 前端，保留原 Logo。
- `deploy/` 低内存预检、ACR 构建说明、原位升级和 Caddy 配置。
- `tests/` 角色迁移、微信注册、任务分配与商家隔离测试。


V2.1.2 三入口及管理员总控制台的说明见 [README_V212.md](README_V212.md) 和 [docs/DOMAIN_ARCHITECTURE.md](docs/DOMAIN_ARCHITECTURE.md)。
