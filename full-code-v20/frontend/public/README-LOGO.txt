黑曼波品牌 Logo 固定资源规范（V2.0 起长期有效）

原始资源路径：
full-code-v15/frontend/public/brand-logo.png

V2.0 构建副本：
full-code-v20/frontend/public/brand-logo.png

两个路径均必须保留有效原始 PNG。所有面板统一使用 /brand-logo.png。
后续版本必须从 V1.5 原始路径复制，不得重绘、替换、裁切、变色或改名。
构建前检查文件存在且非空；缺失时 Docker 构建必须失败。
在开发包根目录执行 ./sync-brand-logo.sh 可同步到 V2.0。
