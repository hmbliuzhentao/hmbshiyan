# 黑曼波工作台 V1.4 · 发布任务与商家视频审核

**版本命名：** `heimanbo1.4`。本包是基于 V1.3 的**完整更新源码**，不是只替换网页样式的补丁，也不是已部署到你的阿里云 ECS 的实例。

## 核心业务流程（与旧版不同）

1. **内部建立商家合作档案及商家登录账号**。不再进行“资质申请／商家审核”；管理员只负责创建、编辑和暂停商家登录权限。
2. **内部在“接单与收款”创建订单**，将订单关联到目标商家。订单记录金额、负责人、成本及收款，现有数据保留。
3. **内部在“发布任务 · 商家审核”创建任务**，必须选择已经关联商家的订单。一个订单允许多个发布任务，一个任务允许多条视频。
4. **制作完成上传视频**：在“上传视频”选择对应发布任务，或在发布任务内直接上传；也可以把内部视频库已有的视频关联到该任务。只有已关联任务的视频才对目标商家可见。
5. **商家使用自己的账号进入工作台**，只看“待审核视频/发布任务、我的合作订单、合作资料”。对每条制作视频选择“审核通过”或“退回修改”，退回须写具体意见。
6. **退回后由内部上传新版本**，原视频审核记录保留，新版本重新进入待审核。任务中的全部当前视频通过后，内部才可登记已发布链接，任务转成已发布。

**注意：** 新版本“审核商家的视频”指 **商家审核黑曼波为其产品制作的视频**，不涉及审核商家经营资格。本次不对接 TikTok 自动发布接口；发布状态和链接由员工人工登记。

## 页面结构

**内部管理工作台**
- 运营总览：总览。
- 订单与发布：接单与收款、发布任务 · 商家审核。
- 视频制作：制作进度、视频素材库、上传视频。
- 商家协作：商家与账号。
- 系统管理：上传记录、员工账号。

**商家工作台**
- 待审核视频 / 发布任务（仅本商家）。
- 我的合作订单。
- 合作资料。

## 数据与权限

新增三张表：`publish_tasks_v14`、`publish_task_videos_v14`、`publish_review_events_v14`。
原有 `users`、`merchants`、`business_orders`、`videos`、`merchant_project_*` 等表**不删除**；项目首次使用 V1.4 后端时由 `Base.metadata.create_all` 新建三张表（仅新增表，不强制清空旧表）。正式持续运营后建议改为 Alembic 数据库迁移。

- 管理员新建发布任务、上传／关联／替换成品视频、登记发布。
- 普通员工可查看内部任务；当前提交／替换视频限制为管理员。
- 商家只能查看自己 `merchant_id` 下的发布任务，不能访问其他商家的任务、视频，不能看内部预估成本或员工报表。
- 商家审核修改意见、审核人和历史状态均记录。替换视频不会抹除旧记录。
- 旧版商家资质审批接口返回 HTTP 410，页面移除了对应入口。旧数据中商家为 `draft/pending/rejected` 时无需重新审核，只有 `suspended` 不允许审核视频；新商家直接进入“合作中”。

## GitHub + 阿里云 ACR 升级（你当前的部署方式）

**先不要运行 `docker compose down -v` 或删除旧卷。**

1. 下载本压缩包，解压后找到 `full-code-v14/`，将**这个文件夹本身**上传至 GitHub 仓库 `hmbliuzhentao/hmbshiyan` 的**仓库根目录**，确保实际路径：
   - `full-code-v14/backend/Dockerfile`
   - `full-code-v14/backend/app/publish_tasks_v14.py`
   - `full-code-v14/frontend/Dockerfile`
   - `full-code-v14/frontend/app/publish-tasks-v14.tsx`
   - `full-code-v14/frontend/app/merchants-v14.tsx`
   - `full-code-v14/frontend/app/page.tsx`
2. **重要：** 猫咪 Logo 的原图需要从已有 GitHub `full-code-v13/frontend/public/brand-logo.png` 复制到新目录 `full-code-v14/frontend/public/brand-logo.png`，再执行构建。这个升级包不重新生成或替换原图。你也可以保留服务器现有 `/opt/heimanbo/brand-logo.png` bind mount；升级脚本不会改 `compose.yaml`。
3. GitHub 私有仓库更适合这类业务后台，切勿上传实际 `.env`、管理员密码或客户文件。
4. 在 ACR **backend** 添加（或编辑）构建规则：`branches:main`，构建上下文 `/full-code-v14/backend`，Dockerfile `Dockerfile`，镜像标签 **`v1.4`**，海外机器构建开启。
5. 在 ACR **frontend** 同样配置：`branches:main`、构建上下文 `/full-code-v14/frontend`、Dockerfile `Dockerfile`、镜像标签 **`v1.4`**。
6. 两个镜像都显示“构建成功”、在**镜像版本**中实际存在 `v1.4` 后，在新 ECS 上传升级包中的 `upgrade_acr_v14.sh` 到 `/opt/heimanbo/`。**PostgreSQL / Caddy 镜像无需重新构建**。
7. 首先确认当前系统能正常运行：

   ```bash
   cd /opt/heimanbo
   docker compose ps
   curl -fsS http://127.0.0.1:8080/api/health
   ```

8. 建议先对 ECS 磁盘或数据库和视频存储卷做快照。升级脚本会额外备份 PostgreSQL 数据和 `.env/compose.yaml/Caddyfile`，**但不会自动复制整个大容量视频数据卷**。确保磁盘容量充足、避免升级时有正在上传的视频。
9. 执行：

   ```bash
   cd /opt/heimanbo
   chmod +x upgrade_acr_v14.sh
   bash upgrade_acr_v14.sh --apply
   ```

   它会从已有 `.env` 的 `BACKEND_IMAGE`、`FRONTEND_IMAGE` 中把 `:v1.3` 升级到 `:v1.4`，执行 DB 备份、镜像拉取和**仅重建前后端容器**。保留所有 Docker volumes 和其余配置（包括 Logo 挂载）。

10. 验收：

   ```bash
   cd /opt/heimanbo
   docker compose ps
   curl -i http://127.0.0.1:8080/api/health
   docker compose logs --tail=50 backend frontend
   ```

   通过你原来的 SSH 隧道访问 `http://localhost:8080`，内部创建测试商家、商家登录账号和订单，分配发布任务，上传测试 MP4，由商家账户审核。验证另一商家看不到该视频。

## 回滚

脚本会显示备份目录 `/opt/heimanbo/backups/before-v14-时间戳/`。如应用启动失败，管理员可将该目录中 `.env` 恢复到 `/opt/heimanbo/.env`（注意权限 600），再执行：

```bash
cd /opt/heimanbo
docker compose up -d --no-deps --force-recreate backend frontend
```

只有在旧 ACR v1.3 镜像仍存在时才适用。**不要自动删除 V1.4 新建的数据表**，避免遗失已新增的审核数据。升级过的数据库不要随意恢复旧备份覆盖后续新增记录。

## 重要限制

- 单次上传视频 ≤ 100 MB，支持 MP4、MOV、WebM；视频格式仅做基础签名校验，不等同杀毒。
- 新增视频审核任务目前只提供站内查看，不自动发送邮件、消息通知，也不自动发布 TikTok。
- 需要商家先拥有内部创建的账号才能审核，不支持匿名审核链接。
- 未在你的真实 ECS 上执行构建或容器端到端测试；已完成 Python 语法检查、离线 TypeScript 语法/基础类型检查及 SQLite + FastAPI 的多商家权限流程测试。
- Next.js V1.3 基础版本含安全更新提示，正式公网开放前应升级依赖、进行安全测试并配置 HTTPS、限速和备份。

## 关键接口

| 身份 | 方法 | 地址 | 说明 |
|---|---|---|---|
| 内部 | GET | `/api/staff/publish-tasks` | 发布任务列表 |
| 内部 | POST | `/api/staff/publish-tasks` | 创建订单关联任务 |
| 内部 | POST | `/api/staff/publish-tasks/{id}/upload` | 直接上传成品 |
| 内部 | POST | `/api/staff/publish-tasks/{id}/videos` | 关联已有视频 |
| 内部 | POST | `/api/staff/publish-tasks/{id}/videos/{link_id}/replace` | 上传修改版本 |
| 内部 | GET | `/api/staff/publish-tasks/{id}/review-history` | 审核历史 |
| 内部 | POST | `/api/staff/publish-tasks/{id}/published` | 审核全通过后登记发布 |
| 商家 | GET | `/api/portal/publish-tasks` | 只看本商家的任务 |
| 商家 | GET | `/api/portal/publish-tasks/{id}/videos/{link_id}/stream` | 权限校验后播放 |
| 商家 | POST | `/api/portal/publish-tasks/{id}/videos/{link_id}/review` | 通过/退回视频 |
