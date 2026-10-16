# 右页 · MIGI

面向 Apple Silicon Mac 的本地漫画阅读器，中文界面，使用 Python、Qt for Python 和 MuPDF。当前统一发布版本 **1.1**。

本仓库整理自已在 MacBook Air M1 / macOS 26.5.1 上运行和打包的 Mac 源码。它不是 Windows 或 Android 发布包；目前不提供经过验证的其他平台构建。

## 功能

- 无 DRM 的 PDF、EPUB、MOBI、ZIP／CBZ、RAR／CBR、7z／CB7 及散图；图书按原路径只读，不复制、不整本解压、不缓存阅读页面。
- 默认日漫右到左、单双页、封面单页、页距、适合窗口／宽度／原尺寸、缩放、跳页及五种翻页效果。
- 独立书库、每页 48 本、搜索／筛选／排序、独立详情；批量混合文件和文件夹、多卷合辑、自然／自定义卷序、每卷进度、扫描新增与重新定位。
- 串行封面子进程，只缓存 420×600 封面小图；支持分卷封面、自选图片与清理缓存。
- 六主题、原生全屏、沉浸上下覆盖浮层。中心点击显隐控件时保持漫画尺寸、位置、缩放和滚动位置。
- 独立计时和日／周／月／年统计。沉浸失焦继续计时；主动暂停、书库／统计暂停、睡眠间隔剔除；合辑不重复累加。
- 自由阅读状态和最多 30 字自定义状态；末页与全卷完成分别确认。
- 单实例激活、Retina PDF 渲染、像素滚动与放大拖动、中文原生文件对话框。

## 运行源码

需要 Apple Silicon Mac、macOS 14 或以上、原生 arm64 Python 3.12。实际验收系统为 macOS 26.5.1；最低版本只表示打包配置要求，未覆盖所有系统版本。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-mac-build.txt
.venv/bin/python reader/tools/prepare_archives.py
.venv/bin/python reader/app.py
```

书库位于 `~/Applications/Migi/Migi-data/data/library.json`，封面位于其 `cache/covers`。源码和独立应用默认共用这个 Mac 书库。开发时可用 `MIGI_DATA_ROOT` 指定独立测试目录，避免改动日常书库。数据目录不能位于 `.app` 内。

## 构建独立应用

```sh
.venv/bin/python scripts/build_macos.py
```

结果是 `dist/Migi.app` 和 `release/Migi-Mac-arm64-v1.1.zip`，无需用户安装 Python。脚本检查原生 arm64 环境、调用 PyInstaller、核对包内 Mach-O 架构并验证本地 ad-hoc 签名，使用 macOS `ditto` 保留链接打包。

本地自用签名不等同于 Apple 公证。公开分发前请根据自己的签名、公证和依赖许可安排重新确认发布方案，不要全局关闭 Gatekeeper。

## 验证

```sh
.venv/bin/python scripts/test_macos.py
# Cocoa 原生独立检查；每次使用一个尚未使用的目录
.venv/bin/python reader/app.py --mac-validation work/acceptance-001
# 构建后也可运行相同检查
./dist/Migi.app/Contents/MacOS/Migi --mac-validation work/frozen-001
```

测试生成合成的中文路径 PDF、EPUB、MOBI。默认不搜索或读取个人图书；可通过 `MIGI_VALIDATION_BOOKS_JSON` 显式提供本地图书路径的 JSON 数组进行额外首／中／末页只读抽查。不要提交这些图书或包含其名称、路径的报告。

完整基线与实测边界见 [验证说明](docs/VALIDATION.md)，打包和发布步骤见 [发布指南](docs/RELEASING.md)。

## 快捷键

⌘O 导入，方向键／空格翻页，Home／End 首末页，F6 书库，Tab 沉浸，Esc／右键退出沉浸；F11 或 Control+Command+F 普通全屏。放大后可滚动或左键拖动平移。

## 已知限制

- 不支持 DRM。复杂 KF8 延续 MuPDF 后备能力，不保证所有 Kindle 文件兼容。
- 实体第二显示器、屏幕切换和实体触控板手感尚未完成硬件验收；DPR=2 检查采用软件强制方式。
- Qt 6.12 的 Cocoa 无障碍表格兼容处理会将封面区作为整体说明提供，不提供逐卡片的原生表格节点；视觉多选、双击、右键与键盘操作保留。
- 多文件夹选择器使用 Qt 对话框，以支持多选；普通文件和单文件夹选择使用 macOS 原生对话框。

## 许可证

项目现按 AGPL-3.0-only 发布，详见仓库根目录 LICENSE 和 NOTICE.md。第三方依赖保留各自许可。下载独立应用见仓库 GitHub Releases；本地自用签名不等同 Apple 公证。

## v1.1 验证依据

本次新增格式已由维护者在 Apple Silicon Mac / macOS 26.5.1 完成 56 项 Cocoa 原生回归；返回记录见 ../docs/MAC_FIX_VALIDATION_2026-10-16.md。独立 .app 另由云端构建并验证架构、签名和打包解码器；源代码实机测试不等同于对云端下载应用的人工实机验收。
