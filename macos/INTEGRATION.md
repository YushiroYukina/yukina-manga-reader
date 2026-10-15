# Mac 1.0.1 整合说明

本目录为 yukina漫画阅读器的 macOS 独立实现，来自维护者提供的 Migi-GitHub-source-v1.0.1.zip。原工程与打包产物名称仍为“右页 · MIGI / Migi.app”，保留这些名称和数据目录以对应已经实机验证的构建；仓库统一项目名称为 yukina漫画阅读器。

源 ZIP SHA-256：`f908a2bde4beceddd718916cdb8bd9c5cff6381b08389ce2888bbdfca758ee87`。导入前核验 77 项原始文件哈希，全部通过。整合时仅将部分 Python/SVG 文件的 CRLF 统一为 LF，以符合随包 .gitattributes，并重建本目录清单；未改动业务逻辑。Windows / Android 源码保持各自目录。

## 已提供的 Mac 实测记录

维护者确认已部署和实机验证。随包 [最新验证报告](docs/VALIDATION_CURRENT.md) 记录 MacBook Air M1 / macOS 26.5.1（25F80）：

- 46 项 Cocoa 原生回归通过。
- 新构建独立 .app 的 86 项验收检查通过。
- 54 个 Mach-O 均支持 arm64，本地 ad-hoc 严格签名检查通过。
- 独立应用子进程管道与第一页封面检查通过。

这些是提供方在 Mac 的验证记录。本次 Windows 整合只核对源 ZIP、清单、语法、目录结构和发布内容，没有在 Windows 重新执行 Cocoa、codesign 或 Mac .app 构建。

## 运行与打包

在 Apple Silicon Mac 上，先进入本目录 macos，再按 [Mac README](README.md) 运行。使用原生 arm64 Python 3.12，最低声明 macOS 14，已实测版本为 macOS 26.5.1。

```sh
cd macos
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-mac-build.txt
.venv/bin/python reader/app.py
# 独立构建，必须在 Mac 执行
.venv/bin/python scripts/build_macos.py
```

源码包没有附带 dist/Migi.app 或可运行的 Mac 发布 ZIP。GitHub 的 Download ZIP 是源码，不是安装包；本次也没有创建软件安装包 Release。若需要向其他人分发独立应用，应上传 Mac 实际生成的包并另行核对签名、公证和许可。

## 数据与范围

默认书库为 `~/Applications/Migi/Migi-data/data/library.json`，只读引用用户本地图书，允许清理封面缩略图，不复制图书或生成页面磁盘缓存。可用 MIGI_DATA_ROOT 指定独立测试目录。Mac、Windows 和 Android 书库各自独立，不自动迁移或云同步。

实体第二显示器和实体触控板手感仍未完成硬件验收；最低 macOS 版本不是逐版本实测保证。详见 [历史验证与边界](docs/VALIDATION.md)。本地 ad-hoc 签名不等于 Apple 公证，项目许可仍待作者选择。
