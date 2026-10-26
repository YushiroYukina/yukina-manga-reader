# yukina漫画阅读器

**v2.0 大版本更新：三端独立在线版。** 在原本地漫画阅读能力的基础上，增加外置书源、混合搜索、在线阅读和主动下载后离线阅读。在线版与原本地版并存，使用各自独立的书库，不自动迁移或覆盖。

当前发布整合 Windows、Android 和 Apple Silicon Mac 的已验收成品。v2.0 是本次整合发行编号；各平台程序内部保留对应的开发预览版本号，具体如下。在线来源仍受网络和站点限制，本版不宣称全部来源或全部作品持续可用。

## 下载安装

展开 [v2.0 发布页的 Assets](https://github.com/YushiroYukina/yukina-manga-reader/releases/tag/v2.0)，按系统下载，也可直接点击：

| 平台 | 安装包 | 内部构建版本 |
|---|---|---|
| Windows 11 x64 | [便携 ZIP](https://github.com/YushiroYukina/yukina-manga-reader/releases/download/v2.0/yukina-online-windows-x64-v2.0.zip) | 0.1.4-windows-preview |
| Android 平板／手机（Android 8.0+） | [安装 APK](https://github.com/YushiroYukina/yukina-manga-reader/releases/download/v2.0/yukina-online-android-v2.0.apk) | 0.1.4-android-preview，versionCode 5 |
| Apple Silicon Mac（macOS 14+） | [arm64 应用 ZIP](https://github.com/YushiroYukina/yukina-manga-reader/releases/download/v2.0/yukina-online-macos-arm64-v2.0.zip) | 0.1.3-preview，Mac build 20261026.4 |
| 完整项目源码 | [源码 ZIP](https://github.com/YushiroYukina/yukina-manga-reader/releases/download/v2.0/yukina-manga-reader-source-v2.0.zip) | 保留三端对应源码及原本地版 |

**Source code 和绿色 Code → Download ZIP 都不是安装包。** 文件校验见发布页 SHA256SUMS.txt，完整变更与验证边界见 [v2.0 更新说明](docs/RELEASE_v2.0.md)。

- Windows：完整解压后运行 YukinaOnline.exe，保留 _internal；已有在线版更新时保留程序旁 online-data。
- Android：安装独立包 cn.yukina.online，不替换原本地版 cn.migi.reader。已有在线版用相同签名直接覆盖安装，避免先卸载而丢失书库及目录授权。
- Mac：解压得到 YukinaOnline.app，仅适用于 Apple Silicon。返回包为本地 ad-hoc 签名、未经 Apple 公证；如被拦截，按系统“隐私与安全性”提示处理，不要全局关闭安全机制。

原本地版 v1.1 与 Android v1.1.1 下载继续保留，说明见 [本地版介绍](README-local.md) 和 [历史发布](https://github.com/YushiroYukina/yukina-manga-reader/releases)。

## 功能与使用方式

- **多书源混合搜索**：到书源管理启用所需来源，发现页同时搜索已启用来源。结果标明出处，某个来源失败时仍保留其他来源结果。
- **统一书库管理**：加入作品后，在书籍详情查看章节，沿用封面、阅读状态、进度、时长及分卷／章节管理；相同作品的不同来源保留各自记录。
- **在线读取与预加载**：默认流畅画质，可选低或原图。画质和预加载入口位于阅读菜单，沉浸浮层中也能打开。收到原图后才进行本地压缩的来源，不会因此减少下载流量；原图档不缩放或重编码。
- **按书下载**：新增下载须进入该书详情的“下载与缓存”，默认只管理这一本书。书库缓存入口只浏览、打开及清理已有完整或部分下载，不提供新下载入口。
- **存储位置可控**：在线页面按需读取并在内存复用，不自动生成页面磁盘缓存；主动下载另选独立目录。Windows 不允许把新下载目录设在 C 盘，Android 可用系统选择器授权 TF 卡文件夹。封面缩略图、书库和设置仍会持久保存。
- **延续本地阅读**：支持 PDF、EPUB、MOBI、ZIP／CBZ、RAR／CBR、7z／CB7、图片及图片文件夹，保留右到左、单双页、页间距、沉浸浮层、翻页效果与阅读计时。主要面向无 DRM 的扫描漫画和图片型书籍；不支持加密或缺卷压缩包，固实归档跳页可能较慢。

移出书库不修改原图书；清理已下载页面是单独操作。更换下载位置后原目录的下载仍可管理。三个平台书库、历史和下载不自动同步，不附带漫画资源。

## 平台与来源差异

| 平台 | 当前内置来源 |
|---|---|
| Windows／Android | MangaDex、漫画柜、MangaPill、包子漫畫.org、ComicABC（公开作品）、MangaKatana |
| Mac | 动漫屋、MangaDex、漫画柜、MangaPill；另提供按来源选择系统连接／直接连接 |

还可连接自行部署的 Komga、Suwayomi 或 Yukina JSON 目录。程序使用固定接口解析，不执行任意网页脚本、Mihon 扩展 APK 或第三方阅读脚本。书源适配代码的开源许可不代表作品内容许可。

**已知网络限制**：Android 本轮网络下 ComicABC 返回 403、漫画柜超时；Mac 实测也保留漫画柜失败提示。MangaKatana 部分章节源站首图留白，程序保留原页序。配置了来源不等于每部作品都能读取，使用者可在书源管理停用不可访问来源。

## 验证与适用范围

- Windows：35 项在线回归、5 项新流程测试、成品 23＋27 项检查通过，另有新增来源的实际封面与正文检查；完整旧桌面测试在无人值守窗口切换时未完成，不计为通过。
- Android：联想 TB371FC／骁龙 870，本轮实际系统为 Android 15 Lineage GSI。39 项基础、63 项协议、15 项真机核对通过；24 页 TF 卡下载全部校验匹配，并完成断网阅读。不能视为 Android 14 ZUI 的本轮复测。
- Mac：维护者返回的 mac4 验收记录包括 13 项交互、38 项在线、10 项动漫屋、56 项本地回归，以及成品 44 项合成流程检查；公网验证范围见返回记录。当前 Windows 侧核对源码完整性、归档、arm64 元数据及校验值，没有重新运行 Mac。

验证是指定设备、样本和时间下的结果，不代表所有设备、作品及来源。详细记录见 [发布说明](docs/RELEASE_v2.0.md)。

## 源码与许可

[online/windows](online/windows)、[online/android](online/android)、[online/macos](online/macos) 分别保存各平台在线版的对应源码与构建入口。根目录 desktop、android、macos 和 VERSION 保留原本地版基线；RELEASE_VERSION 记录整合发行号。构建某平台请先进入对应 online 子目录，不要用原本地版构建入口代替在线版。

源码和成品按 **AGPL-3.0-only** 发布，允许按许可条款使用、修改和再分发，相关义务见 LICENSE。第三方依赖各自保留许可，见 NOTICE.md 与对应平台许可目录。项目与安装包不包含个人书库、下载页面、签名私钥或工具链。

反馈请使用 [GitHub Issues](https://github.com/YushiroYukina/yukina-manga-reader/issues)，附平台、内部版本、来源名称、错误提示和复现步骤；请勿上传漫画文件、账号凭据或个人书库。
