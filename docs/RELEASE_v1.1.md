# yukina漫画阅读器 v1.1

新增 ZIP／CBZ、RAR／CBR、7z／CB7 压缩包扫图、图片文件夹与单张图片。按自然页序只读原书，保留第一页封面、独立／多卷书库、进度、状态和时长。

修复中文目录识别、混合 ./ 前缀页序、重复导入散图文件夹时“跳过”计数遗漏；不改写原文件、不整包解压、不创建页面磁盘缓存。

Windows：完整解压 ZIP 并运行 yukina-reader.exe，保留 _internal。更新时保留原 data 和 cache 目录。
Android：覆盖安装同签名 APK，保留书库；不卸载旧版。
Mac：Apple Silicon arm64，解压得到 Migi.app；本地 ad-hoc 签名，未经 Apple 公证。沿用原 Mac 数据目录，三个平台的书库互相独立。

Windows 56 项自动回归、Android 39 项主机检查、此前 67 项真机检查与真实 TF 卡 ZIP、Mac 返回源码 56 项 Cocoa 原生回归通过。具体样本和限制见验证文档；Mac 新成品另经云端打包及组件检查，不能当作新成品的人工实机验收。

不支持加密、缺卷的分卷压缩包、嵌套压缩包和动图播放；单页文件最大 32 MiB，单本最多 20000 页。固实 RAR／7z 跳页可能较慢。按系统选择 Assets 安装包；Source code 为源码。

源码与成品采用 AGPL-3.0-only，第三方组件保留其许可；见 LICENSE / NOTICE.md。

初版统一称为 v1.0，保留其原有日期标签和下载地址。
