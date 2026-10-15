# macOS 构建交接

这里仅包含 MacBook Air M1 / Apple Silicon 的构建模板；本工作区没有收到 Mac 上继续开发后的源码，也没有 Mac 原生验收结果。不要将此目录描述为已完成的 Mac 版本。

共用源码位于 ../desktop，保留 Windows 功能基线，不迁移任何平台的用户书库。Mac 适配首先需要完成 .app 外部可写数据根、资源路径、字体、多屏/窗口、单实例与全屏行为；当前 desktop 仍是 Windows 基线。

在 Mac 上自行建立虚拟环境、安装 requirements-build.txt；适配完成后复制 Migi.macOS.spec.template 为 Migi.macOS.spec，再用 PyInstaller 构建。模板按新目录结构指向 desktop；不要在 Windows 宣称 .app 已可用。模板最低系统为 14.0，不代表已经测试该系统。

需在 Mac 实测：Finder 双击和二次启动、中文路径三格式、首面封面、单双页与 RTL、窗口/触控板/全屏、计时保存、.app 外的数据路径和签名验证。
