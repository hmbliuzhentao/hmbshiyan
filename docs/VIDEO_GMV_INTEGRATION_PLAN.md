# 黑曼波 V2.2.1 视频数据与 GMV 集成方案

## 当前代码基线

- 仓库：`hmbliuzhentao/hmbshiyan`
- 基线分支：`v2.1.2-www-domain`
- 基线提交：`e9546663539ef9c5a26ea39f0672d603b03825f3`
- 集成分支：`feature/v2.2.1-video-gmv-integration`
- 线上现有版本：V2.1.2（后端镜像含 merchantlocal 修复，前端镜像含 navfix 修复）
- 不直接覆盖线上 Compose、数据库卷或 Caddy。

## 已确认的现有采集源码

用户提供的采集程序包括：

- `yue(1).py`：TikTok 账号/视频采集，原先从腾讯文档或飞书读取账号并写入飞书。
- `tts(1).py`：较新的 TikTok 采集变体，账号源和结果仍依赖飞书多维表格。
- `tiktok2_V9_FastMoss_运营增强版.py`：在 TikTok 采集基础上加入 FastMoss OpenAPI。

现有 TikTok 采集器具备账号主页识别、视频归属校验、视频 ID 去重、发布时间排序、播放/点赞/评论/收藏/分享抓取等能力。当前脚本使用 Windows Microsoft Edge CDP（127.0.0.1:9222）及 Windows 本地路径，不能原样放进 Linux Docker Worker，需要抽离采集逻辑并改造浏览器运行环境。

现有 FastMoss 客户端使用 Bearer API Key，代码中涉及以下接口：

- `POST /creator/v1/search`
- `POST /creator/v1/productList`
- `POST /product/v1/salesTrend`
- `POST /product/v1/videoList`

已有逻辑可取达人资料、28 日 GMV/销量、近 7 日商品，并在 deep 模式下按 video_id 与 uid 精确匹配商品视频 GMV。FastMoss API Key 必须从环境变量/安全配置读取，不能提交到 Git。

## 采集范围配置

首轮测试配置：

- 数据源：both（TikTok 公开账号/视频指标 + FastMoss OpenAPI）
- 采集范围：both（账号档案 + 视频数据）
- 账号数量：100
- 历史数据：最近 7 天

重要边界：现有 Python 源码没有 TikTok Shop 官方 GMV API 集成。TikTok 公开页面采集用于账号与视频公开指标；FastMoss 提供其 API 返回的达人/商品/视频 GMV。若要把 TikTok Shop 官方授权 GMV 作为独立第三数据源，必须另行接入经授权的 TikTok Shop Open API，并配置应用凭证及店铺/创作者授权，不能把 FastMoss 数据标记成 TikTok 官方数据。

## 数据架构

两类采集器独立运行、独立记录来源，结果写入黑曼波 PostgreSQL，不再写腾讯文档或飞书。

建议新增表：

- `tracked_accounts`：待采集账号、账号 UID、启用状态、负责人/店铺标签。
- `collection_jobs`：采集任务、数据源、范围、历史天数、状态、重试次数和错误信息。
- `creator_snapshots`：账号维度的来源快照，保留采集时间、时间窗口、币种及原始响应。
- `video_metric_snapshots`：视频公开指标及来源快照；按来源与视频 ID 去重。
- `product_snapshots`：商品销量、GMV、币种、时间窗口及来源。
- `collector_events`：采集器运行日志和账号级失败原因。

所有金额必须保存币种、来源和统计窗口；不同来源不能直接相加。无数据、未授权、未匹配和真实 0 必须区分。

## Worker 与 API

- 后端继续使用现有 FastAPI、SQLAlchemy、PostgreSQL。
- 新增管理员专用账号管理、采集任务、概览、账号、视频和商品查询接口。
- 新增独立 TikTok Worker 与 FastMoss Worker；两者分别排队、限速、重试和落库。
- 首轮 100 个账号采用低并发队列，按账号隔离错误；避免一次性并发访问。
- Worker 使用专用服务凭证调用后端内部采集 API，不复用管理员 JWT。
- 前端新增管理员可见的“视频数据分析”入口，提供账号、视频、商品、GMV 汇总及采集状态。

## 数据安全与升级要求

- 不删除或重建现有 `heimanbo_v20_db`、`heimanbo_v20_videos` 数据卷。
- 不修改现有订单、商家、管理员和角色权限逻辑。
- 数据迁移仅允许幂等、增量新增表/索引/可空字段；禁止 DROP、TRUNCATE。
- 不提交 TikTok Cookie、FastMoss API Key、Feishu App Secret、Base Token 或任何 .env 文件。
- 旧脚本含有硬编码的飞书凭证；不要复制到新仓库。应在飞书侧轮换这些已暴露凭证。
- 生产切换前先完成有效 PostgreSQL 备份、应用镜像构建和测试；保留当前应用镜像以便回滚。

## 验收标准

1. 原管理员、拍摄剪辑、商家登录和订单流程不回归。
2. 商家数据隔离不受影响；GMV 管理面板仅管理员可见。
3. 同一视频重复采集不产生重复主记录；来源快照可按时间查询。
4. 账号归属校验失败时整条记录拒绝写入，不能串号。
5. 100 个账号按任务队列执行，单账号失败不影响其他账号。
6. TikTok 与 FastMoss 数据来源、币种、时间窗口明确显示。
7. 先用一个有授权的测试账号完成真实采集，再扩大到 100 个账号。
