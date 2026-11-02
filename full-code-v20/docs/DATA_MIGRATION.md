# V1.5 → V2.0 数据迁移原则

## 不覆盖、不共用数据库
V2.0 使用独立 PostgreSQL 数据库和独立 Docker volumes。禁止把 V2.0 的 `DATABASE_URL` 指向 V1.5 数据库；禁止执行 `docker compose down -v`。

## 迁移顺序（正式迁移前必须在副本演练）
1. 对 V1.5 PostgreSQL 做 `pg_dump --format=custom` 完整备份。
2. 单独备份 V1.5 视频卷与商家素材卷；数据库备份不包含文件。
3. 启动 V2.0 数据库容器，先通过 V2.0 ORM 创建完整空 schema（不要启动会自动创建管理员的 backend）。
4. 将 V1.5 数据库数据导出为 data-only，并导入 V2.0 新库；确认新增 User.phone、is_active 等列可使用 NULL/默认值。
5. 对导入的 V1.5 旧账号回填 `UPDATE users SET password_changed_at = COALESCE(created_at, NOW()) WHERE password_changed_at IS NULL;`，以标记旧账号原本已有密码；微信新注册账号保持 NULL。
6. 校验 users、merchants、business_orders、merchant_project_requests、publish_tasks、审核记录、付款记录数量和外键。
7. 将视频/素材文件复制到 V2.0 独立卷，校验 SHA256 和文件数。
8. 启动 V2.0 backend，核对管理员账号、商家账号、订单、视频播放和商家隔离。
9. 验收通过后再安排正式域名切换。

当前交付包没有执行生产数据迁移，也没有连接用户服务器。不得把“源码包已生成”理解为“线上已升级”。
