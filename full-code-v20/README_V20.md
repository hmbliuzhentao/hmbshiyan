# 黑曼波工作台 V2.0 Dev3

本版本针对 896MiB ECS 做低内存单实例部署调整：复用现有 Caddy，不再创建第二个 Caddy；V2.0 前后端加入现有 Caddy Docker 网络，数据库使用独立内部网络和独立数据卷。

部署前先完成 ACR v2.0.0 镜像构建、Spaceship DNS 解析和 Caddy 网络核对。详见 `deploy/INSTALL_LOW_MEMORY.md`。

注意：这是 V2.0 第一阶段业务基线，不代表全部最终功能或生产安全验收已完成。
