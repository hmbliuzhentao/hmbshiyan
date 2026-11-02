# 账号、验证码与微信配置

## 邮箱验证码
配置 `.env`：
- SMTP_HOST
- SMTP_PORT
- SMTP_USERNAME
- SMTP_PASSWORD
- SMTP_FROM
- SMTP_SSL

生产环境不得开启 `OTP_DEBUG`。当前开发模式才允许 `APP_ENV=development` 且 `OTP_DEBUG=true` 时返回调试验证码。

## 短信验证码
当前适配器向 `SMS_GATEWAY_URL` 发送 JSON：
```json
{"phone":"+8613800000000","code":"123456","template_id":"YOUR_TEMPLATE","ttl_minutes":5}
```
请求可带 `Authorization: Bearer SMS_GATEWAY_TOKEN`。该接口是通用适配约定，不是阿里云/腾讯云官方 SDK；选定服务商后必须按它的真实签名、模板参数和响应结构完成适配测试。

## 微信网站扫码登录
在微信开放平台创建并审核通过“网站应用”，设置网站授权域名 `heimanbo.com` 或按平台要求配置根域名。配置：
- WECHAT_APP_ID
- WECHAT_APP_SECRET
- WECHAT_REDIRECT_URI=https://auth.heimanbo.com/api/auth/wechat/callback

AppSecret 只放服务器 `.env`，不得写入前端、GitHub 或聊天。微信首次授权会建立商家账号申请（pending），管理员审核通过后才能使用商家业务功能。

本包实现的是 PC 网站二维码登录 OAuth。公众号网页授权、微信小程序登录、微信支付需分别申请对应资质和接口，不能混为一项。
