# yukina漫画阅读器 v2.0 · 三端独立在线版

相较此前公开的本地版 v1.1／Android v1.1.1，本次新增三端独立在线应用：可配置多个书源、混合搜索、加入书库在线阅读，并在自行选择的目录下载后离线阅读。原本地版与历史下载继续保留，在线版不覆盖原程序，也不自动迁移原书库。

**v2.0 是整合发行编号，在线功能仍具有开发预览性质。** 为保持已验收成品与对应源码一致，程序内部保留 Windows 0.1.4-windows-preview、Android 0.1.4-android-preview，以及 Mac 0.1.3-preview / build 20261026.4。本次没有在 Windows 重新构建或修改已签名的 Mac 应用。

## 下载与安装

| 平台 | 成品下载 | 对应源码 |
|---|---|---|
| Windows 11 x64 | [便携 ZIP](https://github.com/YushiroYukina/yukina-manga-reader/releases/download/v2.0/yukina-online-windows-x64-v2.0.zip) | [Windows 源码](https://github.com/YushiroYukina/yukina-manga-reader/releases/download/v2.0/yukina-online-windows-source-v2.0.zip) |
| Android 8.0+ 平板／手机 | [安装 APK](https://github.com/YushiroYukina/yukina-manga-reader/releases/download/v2.0/yukina-online-android-v2.0.apk) | [Android 源码](https://github.com/YushiroYukina/yukina-manga-reader/releases/download/v2.0/yukina-online-android-source-v2.0.zip) |
| Apple Silicon Mac，macOS 14+ | [arm64 应用 ZIP](https://github.com/YushiroYukina/yukina-manga-reader/releases/download/v2.0/yukina-online-macos-arm64-v2.0.zip) | [Mac 返回源码](https://github.com/YushiroYukina/yukina-manga-reader/releases/download/v2.0/yukina-online-macos-source-v2.0.zip) |

也提供包含原本地版和三端在线版的 [完整项目源码](https://github.com/YushiroYukina/yukina-manga-reader/releases/download/v2.0/yukina-manga-reader-source-v2.0.zip)。**Source code 是源码，不是安装包。** 文件完整性请对照附件 SHA256SUMS.txt。

- Windows：完整解压，运行 YukinaOnline.exe，保留 _internal。已有在线版请保留程序旁 online-data 及原下载目录。
- Android：独立包名 cn.yukina.online，与本地版 cn.migi.reader 并存。已有在线版可使用本包同签名覆盖升级，不要先卸载。
- Mac：解压得到 YukinaOnline.app，仅 arm64，不适用于 Intel Mac。本地 ad-hoc 签名、未经 Apple 公证；按系统“隐私与安全性”提示处理拦截，不要全局关闭 Gatekeeper。已有在线版保留原数据和下载目录。

## 主要变化

1. **混合搜索与来源管理**：发现页搜索所有已启用来源，结果保留来源。来源可分别启停；慢源或失败来源不会清空其他来源已经返回的结果。
2. **在线与离线同一书库**：加入作品后沿用书籍详情、章节／分卷、封面、阅读状态、进度和阅读时长。相同作品的不同来源保留各自书库记录。
3. **下载入口按书籍收拢**：到具体书籍详情打开“下载与缓存”，默认仅管理该书。书库缓存入口只浏览、打开、清理已有完整或部分下载；要新下载先进入该书详情。继续本书队列时保留其他书的待下载记录。
4. **阅读内画质与预加载**：在阅读菜单打开，沉浸浮层同样可用。默认流畅，另有低、原图档；原图不缩放和重编码。预读页面只留内存，只有主动下载才保存章节页面。对于接收原图后再压缩的来源，不宣称节省网络流量。
5. **保留原文件与独立存储**：本地书继续按原地址只读，移出书库不改动原文件。下载另选独立目录，Windows 禁止新缓存设在 C 盘，Android 可授权 TF 卡。封面缩略图、书库、设置和计时仍会持久保存。
6. **延续漫画阅读体验**：右到左、单双页、页间距、沉浸浮层、多种翻页效果、状态标记和计时统计继续保留。支持原本地格式；无 DRM、扫描版与图片型漫画为主要使用范围。

## 三端来源与适配差异

Windows／Android 内置 MangaDex、漫画柜、MangaPill、包子漫畫.org、ComicABC（公开作品）、MangaKatana。Mac 保留已验收的动漫屋、MangaDex、漫画柜、MangaPill，并可按来源选择跟随系统连接或直接连接。三端不强行合并不同的来源配置，也不自动同步书库、历史或下载。

另可接入自行部署的 Komga、Suwayomi 服务或 Yukina JSON 目录。应用采用固定接口解析，不执行任意网页或阅读脚本，不直接加载第三方扩展 APK。来源代码开源不等于作品内容授权。

## 验证依据

| 平台 | 结果与范围 |
|---|---|
| Windows | 35 项在线回归、5 项新增流程、成品 23＋27 项检查通过，并检查实际来源的封面和正文。完整旧桌面回归在无人值守窗口切换时未完成，不计为通过。 |
| Android | 联想 TB371FC／骁龙 870，本轮系统实际为 Android 15 Lineage GSI。39 项基础、63 项协议、15 项真机核对通过；TF 卡下载 24 页全部 SHA-256 匹配，关闭 Wi-Fi 后离线打开成功。不能作为原 Android 14 ZUI 的本轮复测。 |
| Mac | 依据维护者返回的 mac4 原生验收记录：13 项新增交互、38 项在线、10 项动漫屋、56 项本地回归，以及源码与成品各 44 项合成流程通过。公网检查限于记录列明的来源和操作；当前 Windows 侧只复核源码清单、归档、arm64／版本元数据和校验值。 |

Mac 返回记录说明：混合来源、下载、清理与队列隔离主要使用合成样本验收，不代表逐部作品通读或对实际用户书库执行过下载／清理。Android 本轮未在真机单独执行跨书并发队列暂停／继续或删除实书缓存，队列隔离另有生产 Java 主机检查。各平台的单次通过均不代表全部设备和网络环境。

## 已知限制

- 当前安卓网络下 ComicABC 返回 403、漫画柜连接超时；Mac 记录也包含漫画柜失败。可在来源管理停用当前不可访问的来源。配置了来源不等于所有作品均可用。
- MangaKatana 部分源站首图留白，程序保留页序，可自行更换封面；登录限定、下架、缺失作品不会绕过限制读取。
- 画质、预加载和内存命中会影响体验，不能保证每次在线翻页即时完成。下载暂停需等待正在进行的网络请求返回。
- 不支持 DRM、加密或缺卷归档；固实 RAR／7z 跳页可能较慢，不提供三端书库或下载自动同步。
- Windows／Mac 成品使用当前已验收构建，不附带面向所有系统的稳定性保证。Mac 历史交接文档中的“尚未验收”文字不覆盖最新 mac4 返回记录。

## 开源与反馈

源码及成品采用 AGPL-3.0-only，第三方依赖保留其许可；对应源码位于 online/windows、online/android、online/macos，原本地版代码继续保留。安装包与源码不包含个人图书、书库、下载页面或签名私钥。

问题反馈：[GitHub Issues](https://github.com/YushiroYukina/yukina-manga-reader/issues)。请附设备／系统、程序内部版本、来源名称、错误提示及复现步骤；不要发送漫画文件、个人书库或凭据。
