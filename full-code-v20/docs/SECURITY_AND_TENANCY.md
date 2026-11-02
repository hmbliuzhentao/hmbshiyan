# 权限与租户隔离设计

## 核心规则
- 商家用户通过 MerchantAccount 关联一个 Merchant。
- 商家订单、发布任务、项目素材和审核接口沿用 V1.5 的 merchant_id 过滤。
- V2 WorkspaceItem 在查询时由后端读取当前 Merchant ID，并追加 `merchant_id = current_merchant.id` 条件。
- 商家不能提交或覆盖 merchant_id 来访问其他商家资源。
- 商家只能创建 product / brief / asset 类型资料；其他内部资料由员工创建。
- 视频流/下载仍必须通过受保护的任务视频接口，不开放 public bucket 或静态目录列表。
- 管理员与员工的财务数据不返回给商家端。

## 角色
super_admin、admin、manager、producer、editor、viewer、merchant。

## 需要上线前继续完成
- 对全部 API 做角色矩阵和 IDOR 自动化测试。
- 关键写操作记录 audit_logs。
- 短信服务商签名验签、验证码发送 IP/设备维度限流。
- 管理员 TOTP/WebAuthn MFA。
- 登录失败封禁与 IP/设备风险策略（当前为单进程 IP 限流，不能替代 WAF/网关限流）。
- 媒体对象存储签名 URL 和下载审计。
