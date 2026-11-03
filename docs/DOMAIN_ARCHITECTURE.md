# V2.1.0 单域名面板架构

当前测试主站统一使用 `test-v2.heimanbo.com`。登录后由账号角色决定显示的工作台：

- `admin`：全站管理、订单、商家、人员、任务分配、视频与统计。
- `producer`：仅显示“我的拍摄剪辑任务”，访问后端分配任务接口。
- `merchant`：仅显示当前商家的订单、需求和视频审核。

Caddy 将 `/api/*` 转发至 `heimanbo-v20-backend:8000`，其余路径转发至 `heimanbo-v20-frontend:3000`。沿用现有 Caddy 容器和共享 Docker 网络，不新增 Caddy 监听端口。

未来如需拆分 auth/work/video/merchant 子域名，可在同一鉴权与租户策略下再配置；本版本先保证用户当前使用的 test-v2 域名完整可用。
