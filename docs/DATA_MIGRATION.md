# V2.0 → V2.1.0 原位数据迁移

V2.1.0 沿用 V2.0 的 PostgreSQL 数据库、视频命名卷、容器名和 Caddy 网络，目的是原位升级，不新建空数据库。

## 启动时的幂等迁移

1. `Base.metadata.create_all` 只创建缺失表。
2. 为 `publish_tasks_v14` 增加 nullable `assigned_user_id`、`assigned_at`、`accepted_at` 和索引；旧任务保留原行，初始为待管理员分配。
3. 兼容旧订单表缺失的 `merchant_id` 字段（仅添加，不重建表）。
4. 角色映射：`super_admin` → `admin`；`manager` / `editor` / `viewer` / 未知角色 → `producer`；`merchant` 保持。
5. 商家状态 `pending` / `draft` / `changes_requested` 转为 `approved`；明确 `rejected` / `suspended` 的历史账号继续保持不可用，不会被自动恢复。

## 数据保护边界

- 不执行 DROP TABLE、TRUNCATE、DELETE 业务记录或 `docker compose down -v`。
- 不在升级迁移时清理历史已发布视频；仅在 V2.1 上线后，商家主动点击“确认已发布”时，才按 `DELETE_MEDIA_AFTER_MERCHANT_CONFIRMATION` 清理该任务当前交付文件，数据库元数据与审核历史保留。
- 不更改现有 `heimanbo_v20_db`、`heimanbo_v20_videos` 命名卷。
- 不更改 PostgreSQL 数据库名、用户、密码、JWT_SECRET 或管理员密码。
- 新增任务分配字段为空时，旧任务仍可由管理员查看并重新分配。

用户明确要求不做备份。本版本按该要求不生成数据库/视频卷备份；这意味着升级期间没有数据级回滚点。上线前请确保能接受这一风险。应用回滚与数据回滚不是同一件事。
