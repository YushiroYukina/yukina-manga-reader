# Mac 1.0.1 源码整合

维护者提供已在 MacBook Air M1 / macOS 26.5.1 上部署、打包并实测的完整源码。报告记录 46 项 Cocoa 回归、新独立应用 86 项检查、54 个 Mach-O arm64 与 ad-hoc 签名验证通过。详见 [Mac 最新报告](../macos/docs/VALIDATION_CURRENT.md) 和 [整合说明](../macos/INTEGRATION.md)。

本次 Windows 侧只验证源 ZIP 的 77 项原始哈希、整合后的代码语法和清单，无 Mac 原生重测；包中不含 .app 安装包。后文“Mac 未验证”仅为源码到达前的历史状态，以本节为准。

# 软件名称更新 · 2026-10-15

显示名称统一为 yukina漫画阅读器：Windows 标题/书库/统计品牌、Android launcher label、Mac .app 模板和仓库说明。内部目录、Windows 既有 EXE 文件名、Android 包名及签名不变，避免破坏更新与现有数据。Mac 仍需目标机验证。

Windows 源码隔离副本 46 项测试通过，Android 24 项主机检查及签名验证通过，已以原签名覆盖安装平板。本次未重新打包正在使用的 Windows EXE，名称变更随下次 Windows 构建生效。

# 验证范围 · 2026-10-15

Android 最近一轮在 Lenovo TB371FC / Android 14 真机通过 49 项检查，主机规则检查 24 项通过。含三格式样本解码/源哈希、横竖屏、浮层、计时、批量合辑、移除卷和跟手翻页。实际 TF 卡 EPUB 曾打开并正确显示封面。连续帧率及全部真实图书兼容性没有全面测试。
Windows 既有基线为 46 项测试通过；本次在隔离的源码副本上重新执行全部 46 项测试通过（offscreen），未修改原书库或运行中程序；不等价于新的 Mac 运行验证。Mac 未在本工作区进行原生打包或运行验证，本包也没有声称包含外部 Mac 工作中的最新改动。
源码包的本次检查结果见 SOURCE_AUDIT.json；原有截图、设备序列号、个人书名、历史调试日志不随此包分发。
