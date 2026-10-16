# Mac v1.1 整合与验证

基于维护者交付的已验证 Mac 工程，保留原生快捷键、Cocoa 对话框、全屏、Retina、单实例及独立数据目录。v1.1 接入 ZIP／CBZ、RAR／CBR、7z／CB7、散图文件夹和单张图片。

2026-10-16 收到修正版源码，原包 SHA-256：151210dab709d08674a2b9e08354018e429d66ee7bfad1411bcb8216bfc39ef7。输入包已验证外层 104 项、Mac 内层 83 项哈希。业务修改为 image_books.py 的页序比较和 reader.py 的重复导入统计，新增五项回归；其余为记录与清单。

维护者在 Apple Silicon / macOS 26.5.1（25F80）完成 56 项 Cocoa 原生回归，未重新构建独立应用或做新增 frozen 阅读检查。原始记录完整保留于 ../docs/MAC_FIX_VALIDATION_2026-10-16.md。

v1.1 的 Mac 应用由 GitHub Apple Silicon 环境重新打包，检查 arm64、ad-hoc 签名与内置解码器；云端打包和辅助进程缩略图检查不等同本次新下载应用的人工实机通读。内部应用名 Migi.app 与原 Mac 数据路径保留，外部发布编号统一为 v1.1。

源码不包含下载的解码器二进制；source 运行前执行 reader/tools/prepare_archives.py，独立应用构建时会自动准备并随包携带。原书只读，只允许封面小图缓存。
