# 黑曼波工作台 V1.5 —— 商家发单 / 商家审核

## 本次业务流程调整

1. **商家工作台 → 发布订单**：商家填写产品、视频条数、比例、时长、拍摄剪辑要求、期望日期和参考链接，创建待报价的订单申请。商家可上传产品素材。这个阶段还不是已确认金额的正式订单。
2. **内部工作台 → 商家订单处理**：工作人员查看商家订单申请及素材，确认需求、报价/接单（转为正式订单），或填写原因拒绝。内部不再有“新建订单”按钮，原 `POST /api/orders` 也被禁止。
3. **商家工作台 → 发布任务 / 审核视频**：商家选择自己已经确认的正式订单，创建发布任务，写明平台、账号及要求。没有正式订单不能发布任务，其他商家的订单无法被选择或利用 API 引用。
4. **内部工作台 → 商家任务 · 上传成品**：只接收商家发布的任务、从视频库关联已完成的视频或上传视频；不可新建任务。商家在自己的任务内预览成品，选择审核通过或退回修改。
5. **商家发布实际视频并记录**：全部视频审核通过后，商家可填写实际发布 URL 并登记“已发布”。内部可看发布结果和统计，但不能代商家登记发布。
6. **订单与收款**：内部订单台账继续保留财务管理、收款、状态修改、数据统计和导出；这些内部成本/利润不会返回给商家。

旧数据与既有历史发布任务保留；这版**没有变更数据库表结构**，因此无需删除数据或重建 PostgreSQL。旧任务仍可查看并完成审核。

## 页面变化

**商家**：发布订单｜发布任务 / 审核视频｜我的合作订单｜合作资料。

**内部**：订单台账与收款｜商家订单处理（报价接单）｜商家任务 · 上传成品｜视频素材库｜员工管理。

## 升级到当前阿里云 ACR 服务器

当前环境采用 `/opt/heimanbo/compose.yaml`、`.env` 和 ACR 镜像。**不要删除 Docker volumes，不要直接重新创建数据库。**

### A. 上传完整代码到 GitHub

从 `heimanbo1.5.zip` 解压出 `full-code-v15`，将其放到 GitHub 仓库 `hmbliuzhentao/hmbshiyan` 的根目录。确保路径：

- `/full-code-v15/backend/Dockerfile`
- `/full-code-v15/backend/app/main.py`
- `/full-code-v15/frontend/Dockerfile`
- `/full-code-v15/frontend/app/page.tsx`
- `/full-code-v15/frontend/public/README-LOGO.txt`

**注意 Logo：** 原猫咪 PNG 图片需要从 V1.4 的 `frontend/public/brand-logo.png` 复制到 `/full-code-v15/frontend/public/brand-logo.png`；本压缩包未包含原图。新版 Dockerfile 自动保证 `/app/public` 存在，不会再因目录不存在构建失败。

不要上传真正的 `.env`、数据库密码、JWT 密钥和客户视频。强烈建议 GitHub 仓库设为私有。

### B. ACR 构建两个镜像

将 `heimanbo/backend` 构建规则设为：
- Branch `main`
- Context `/full-code-v15/backend`
- Dockerfile `Dockerfile`
- Tag `v1.5`
- 海外构建开启

`heimanbo/frontend` 对应：
- Branch `main`
- Context `/full-code-v15/frontend`
- Dockerfile `Dockerfile`
- Tag `v1.5`
- 海外构建开启

等待两次构建均显示**成功**，并在镜像版本中看到 `v1.5`。PostgreSQL 和 Caddy 使用现有镜像，不重建。

### C. 在服务器更新应用镜像

将 `upgrade_acr_v15.sh` 上传到 `/opt/heimanbo/`。备份数据库、视频数据卷或创建 ECS 快照（该脚本自动备份数据库及运行配置，**不自动备份视频数据卷**）。先检查镜像设置：

```bash
cd /opt/heimanbo
docker compose ps
docker compose config --images
```

确认服务器没有正在进行的视频上传或订单修改，再运行：

```bash
chmod 700 /opt/heimanbo/upgrade_acr_v15.sh
cd /opt/heimanbo
bash upgrade_acr_v15.sh --apply
```

脚本会先通过 ACR 拉取 `v1.5` 前后端镜像，成功后才备份数据库、切换 `.env` 并重新创建**仅前后端**容器。若拉取失败，不触碰旧服务；切换失败将尽力恢复原镜像和配置。绝不执行 `docker compose down -v`。

**如果旧的 V1.4 升级失败、服务器当前仍运行 V1.3**，脚本也允许从 V1.3 直接切换到 V1.5。务必以 `docker compose config --images` 为准。

### D. 验证

```bash
cd /opt/heimanbo
docker compose ps
curl -i http://127.0.0.1:8080/api/health
curl -I http://127.0.0.1:8080/
docker compose images
```

验证端到端操作：管理员创建商家账号 → 商家发布订单申请 → 管理员接单报价 → 商家创建发布任务 → 内部上传成品 → 商家审核/退回 → 商家记录已发布链接 → 内部统计。另用第二个商家账号验证数据不能串户。

## 权限/安全注意

- 仅对应商家可创建本商家的发布任务、审核其任务视频、登记发布。
- 内部可报价确认、绑定成品，但直接创建订单/发布任务/登记发布的旧接口现在返回 403。
- 重要：这是业务流程升级，不是公开互联网环境的完整安全审计。正式公网开放前还应完善 HTTPS、登录限速、文件格式校验、视频存储备份和依赖安全升级。
- 前端原版 Next.js 15.5.6 有安全版本提示，正式上线前应升级至经测试的修复版本。

## 验证范围

已完成 Python 编译语法检查、TypeScript/TSX 语法检查，以及 SQLite + FastAPI TestClient 权限和交易流程回归测试。**未在你的真实 ECS 和 ACR 中构建部署。**
