# 独立在线版源码

本目录按平台保留已验收的源代码，避免把一个平台的调整覆盖到另一平台。

| 目录 | 对应成品内部版本 | 构建入口 |
|---|---|---|
| windows | 0.1.4-windows-preview | tools/build_windows.py |
| android | 0.1.4-android-preview / versionCode 5 | android/tools/build.py |
| macos | 0.1.3-preview / Mac build 20261026.4 | macos/build_macos.py |

各目录中的 SOURCE_MANIFEST.json 为其原始交付清单，可从对应目录执行 tools/verify_source.py。Mac 目录保留返回源码与验收记录对应的内容，本次未在 Windows 重新构建 Mac。

源码、安装包与发布范围见仓库根目录 README.md、docs/RELEASE_v2.0.md。Mac 旧文档中的待验收文字为历史交接说明，当前结论以 docs/v2.0/Mac交互调整与验收记录.md 中的 mac4 结果为准。

应用与数据均独立于原本地版；不同平台的来源类型和连接设置有差异，不应将某平台全部配置直接覆盖到另一平台。平台源码树之间不自动合并。
