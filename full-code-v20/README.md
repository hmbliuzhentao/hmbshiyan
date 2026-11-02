# 黑曼波工作台 V2.0

V2.0 独立开发目录。请先阅读仓库根目录 `README_V20.md` 及 `docs/` 中的域名、认证、数据迁移和部署说明。

- 多面板域名：auth / work / video / merchant / system。
- 统一后端与数据库，按域名和角色限制面板访问。
- 账号：手机号/邮箱密码登录、OTP 注册与重置、联系方式绑定、微信网站扫码 OAuth 框架、会话管理。
- 资料模块：产品、brief、脚本、分镜、提示词、素材、备注。
- V1.5 原业务保留在 `/legacy-v15`，订单/商家/视频任务/审核接口继续复用。
- 商家资料查询必须由后端按 merchant_id 隔离。
- Logo 原始源路径：`full-code-v15/frontend/public/brand-logo.png`；用仓库根目录 `./sync-brand-logo.sh` 同步到本目录。

本包为 Phase 1 开发基线，外部短信/SMTP/微信凭据、完整生产验收和 V1.5 数据迁移尚未完成。
