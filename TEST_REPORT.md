# V2.1.0 本地验证报告

## 已通过

- Python 后端 `compileall`：通过。
- `tests/test_v21_startup.py`：启动、幂等迁移、默认管理员创建、孤立商家账号自动关联：通过。
- `tests/test_v21_auth_workspace.py`：三角色迁移、关闭公开 OTP 注册、商家工作区隔离、管理员启停账号：通过。
- `tests/test_v21_wechat_oauth.py`：商家/拍摄剪辑微信注册、无需审核、角色锁定、单次 OAuth state：通过（微信接口使用模拟响应，不代表真实微信平台已接通）。
- `tests/test_v21_assignment_isolation.py`：管理员分配、拍摄剪辑接单、任务隔离、商家 A/B 视频隔离、审核/替换新版、商家确认发布后清理物理文件：通过。
- `tests/test_v21_additive_migration.py`：模拟 V2.0 旧表，验证增加任务分配字段后保留任务与商家记录：通过。
- `tests/test_merchant_order_v15.py`：原有订单、商家审核和发布流程回归：通过。
- TypeScript/TSX 语法解析：7 个文件，0 个语法解析错误。
- Compose YAML 解析：通过；确认仍沿用 `heimanbo_v20_db`、`heimanbo_v20_videos` 原数据卷名称。
- 部署 shell 脚本 `bash -n`：通过。

运行后端测试：

```bash
bash scripts/test-v21.sh
```

## 尚未验证 / 未执行

- 完整 Next.js 类型检查与生产构建：当前执行环境没有 `node_modules`，`npm install` 超时，离线缓存也不可用；因此不能宣称前端生产构建已通过。
- Docker 镜像构建：当前执行环境没有 Docker CLI。
- ACR 镜像推送：没有用户的 ACR 登录授权。
- 美国 VPS 线上部署与 Caddy reload：当前执行环境没有 SSH 客户端和服务器授权，未连接、未修改线上容器。

因此，本报告证明后端测试和配置静态检查通过，不等于已经完成线上部署或微信真实授权验收。
