# 品牌 Logo 固定资源规则

用户提供的原始 PNG 已纳入本开发包，SHA-256：
`93a520cc3c7db289a5144edf1d3ff38982693905999cde6c4eebac1727186874`

唯一原始资源源路径：
`full-code-v15/frontend/public/brand-logo.png`

V2.0 构建副本：
`full-code-v20/frontend/public/brand-logo.png`

后续每个版本都必须从上述 V1.5 原始路径复制原文件到自己的 `frontend/public/brand-logo.png`，页面统一使用 `/brand-logo.png`。不得重新生成、替换、改名、裁切或变色。

同步命令：在开发包根目录执行 `./sync-brand-logo.sh`。
构建前必须检查文件存在且非空；缺失时 Docker 构建必须失败。
