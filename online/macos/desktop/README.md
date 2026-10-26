# yukina漫画阅读器 · 在线版桌面端

这是独立在线版的 Windows / Mac 共用 Qt 阅读器。功能与运行步骤见项目根目录 README.md；Mac 交接见 macos/README.md。

数据目录通过 platform_support.runtime_root() 独立选择，不读取原本地阅读器默认书库。在线适配与下载见 online_core.py；异步界面见 online_ui.py；显式隔离验收见 online_validation.py。原有本地格式、布局、计时和状态代码仍保留。
