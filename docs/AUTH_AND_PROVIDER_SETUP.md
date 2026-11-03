# V2.1.0 账号、微信授权与服务配置

## 角色与注册规则

- 管理员：只能由已登录管理员在后台创建；公众微信注册不允许选择管理员。
- 拍摄剪辑：登录页选择“拍摄剪辑”，通过微信网站扫码授权首次注册；无需人工审核。
- 商家：登录页选择“商家”，通过微信网站扫码授权首次注册；系统自动建立商家档案并立即启用，无需人工审核。
- 已绑定的微信 openid 后续登录时始终使用原账号角色，不会因用户再次选择另一个注册按钮而切换角色。
- 新账号不设置可用密码；旧账号的密码登录保留兼容。OTP 注册入口已关闭，OTP 仅用于已有账号的密码重置/联系方式绑定。

## 微信开放平台配置

企业主体在微信开放平台创建并审核通过“网站应用”，网站授权域名按平台审核要求填写 `heimanbo.com` / `test-v2.heimanbo.com`。部署环境配置：

```dotenv
PUBLIC_APP_URL=https://test-v2.heimanbo.com
WECHAT_APP_ID=微信开放平台的 AppID
WECHAT_APP_SECRET=微信开放平台的 AppSecret
WECHAT_REDIRECT_URI=https://test-v2.heimanbo.com/api/auth/wechat/callback
DELETE_MEDIA_AFTER_MERCHANT_CONFIRMATION=true
```

AppSecret 只放美国 VPS 的 `.env`，不要写入前端、GitHub、截图或聊天。`/api/auth/providers` 在 AppID 与 AppSecret 均配置后才返回 `wechat: true`。

微信扫码使用 PC 网站应用 `snsapi_login`。公众号内网页授权、小程序登录、微信支付均为不同产品能力，需要单独申请和开发。

## 其他认证服务

邮箱 SMTP 与短信网关配置仍可用于已有账号的联系方式绑定/密码重置；它们不再用于公开注册。生产环境必须保持 `OTP_DEBUG=false`。
