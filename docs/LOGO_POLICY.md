# 品牌 Logo 固定资源规则

V2.1.0 包内的 `frontend/public/brand-logo.png` 是本版本唯一使用的品牌 Logo 资源。

SHA-256：`93a520cc3c7db289a5144edf1d3ff38982693905999cde6c4eebac1727186874`

所有角色面板统一引用 `/brand-logo.png`。不得重新生成、替换、改名、裁切或变色。构建前必须检查文件存在且非空；缺失时 Docker 构建必须失败。
