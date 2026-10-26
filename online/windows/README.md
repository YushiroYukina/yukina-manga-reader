# yukina漫画阅读器 · 在线版

独立 Windows 更新 **0.1.4-windows-preview**。与原本地阅读器使用不同程序和书库，可并存。本次只更新 Windows；Android 等连接平板后适配，Mac 源码不在本次修改范围。

## 本次更新

- 新增包子漫畫.org（中文）、ComicABC（中文公开作品）、MangaKatana（英文），连同漫画柜、MangaDex、MangaPill 共六个内置来源。
- 在线发现同时搜索已启用来源，结果标明出处；到「书源管理」启停来源。某个来源失败时，其余成功结果仍可使用。
- 在具体书籍详情点击「下载与缓存」，选择该书章节下载、继续队列或清理。操作不会覆盖其他书籍的待下载队列。
- 书库「下载与缓存」只浏览、打开及清理已有下载；需要新下载时，先进入该书详情。
- 「在线画质与预加载」移到阅读菜单，沉浸阅读浮层内同样可用。提供低、流畅（默认）、原图三档及可选预加载。

## 使用

完整解压 Windows 包，运行 `YukinaOnline.exe`。打开「在线发现」搜索，加入书库后在详情选择章节阅读。首次升级会补齐新增来源，保留现有来源设置。之后手动移除的来源不会每次启动重复恢复。

在线页面按需读取，仅驻留内存；只有主动下载才保存章节文件。先选择独立下载目录，Windows 不允许新缓存配置在 C 盘。程序旁 `online-data` 保存书库、阅读记录、设置及封面缩略图。更新时保留此目录。移出书库不删除原书，清理下载另有入口。

继续保留右到左、单双页、页间距、翻页动画、沉浸阅读、阅读状态、分卷管理与阅读计时。本地文件仍按原地址只读。不同平台书库不自动同步。

## 书源边界

书源受网络、地区和站点变更影响，不保证每部作品可用。ComicABC 仅支持公开作品，登录限定结果会过滤。包子漫畫.org 与 www.baozimh.com 是不同网站，部分已下架作品没有章节。MangaKatana 实测某章节首图由源站返回留白，后续正文正常；程序保留源站页序，可另选封面。

适配器参考 Keiyoushi 开源扩展的端点与固定解析规则，不执行网页或扩展中的任意脚本，不绕过登录限制。书源代码的开源许可不代表作品内容的许可。另支持连接自行部署的 Komga、Suwayomi 或 Yukina JSON 目录。详见 [书源说明](docs/SOURCES.md)。

## 从源码构建 Windows

```powershell
python -m pip install -r desktop/requirements.txt
python -m pip install PyInstaller
python desktop/tools/prepare_archives.py
python desktop/app.py
python tools/build_windows.py
```

本次使用 Windows x64、Python 3.10、PySide6 6.12 验证。源码包不含工具链、私钥、个人书库或漫画页面。运行 `python tools/verify_source.py` 可检查源码清单。实测与局限见 [Windows 更新说明](docs/WINDOWS_UPDATE.md)。

程序源码按 AGPL-3.0-only 发布，第三方许可见 LICENSE、NOTICE.md 和 licenses。
