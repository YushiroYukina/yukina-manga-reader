# yukina漫画阅读器 · Android 独立在线版

版本 **0.1.4-android-preview**，独立包名 `cn.yukina.online`，可与本地版 `cn.migi.reader` 并存。不会迁移或覆盖本地版书库。

## 本次更新

- 六个内置来源：MangaDex、漫画柜、MangaPill、包子漫畫.org、ComicABC（公开作品）、MangaKatana。
- 同时搜索已启用来源；在书源管理启停来源。来源失败时保留其他来源的成功结果。
- 图书详情的「下载与缓存」只管理该书；继续队列按书籍隔离，保留其他书籍任务，失败章节仍留在队列。
- 书库缓存入口只浏览、打开和清理已有下载，提供进入书籍详情的入口，不直接创建新下载。
- 画质和预加载位于阅读菜单，含沉浸浮层。默认流畅，可选低、原图；只在内存中预读，主动下载才落盘。
- 缓存页面新增刷新按钮；更换下载路径前需暂停任务。TF 卡使用系统文件夹授权，只在自行选择的目录中创建 YukinaOnlineDownloads。

保留右到左、单双页、页间距、沉浸阅读、翻页效果、阅读状态、封面、计时和分卷管理。本地原书只读，移出书库不改动原文件。完整离线章节可在来源停用后打开。

## 安装与构建

APK：`dist/yukina-online-android-v0.1.4-preview.apk`。已有在线版请用相同签名覆盖安装，保留应用数据和下载目录；不要卸载后再装。本次在 Windows 使用 JDK 21、SDK 34、Python 构建。

```powershell
python tools/bootstrap.py
python tools/build.py
```

也可设置 `YUKINA_ANDROID_TOOLS` 指向已准备的工具目录。密钥、工具链、个人书库和下载页面不随源码分发。基础规则检查随构建执行，生产 Java 协议检查使用项目根目录的 `tools/test_android_protocol.py`。

## 实测范围与局限

联想 TB371FC，本轮实际连接的系统为 Android 15 / Lineage GSI，不等同于原 Android 14 ZUI 验证。39 项基础检查、63 项协议检查通过。真机过程和书源限制见 `../docs/ANDROID_UPDATE_VALIDATION.json`。

网络实测中 ComicABC 返回 403，漫画柜连接超时；已配置不代表当前网络下所有来源都可用，可在书源管理停用。MangaKatana 部分章节由源站返回留白首图，程序保留原页序。书源可用性随作品、网络和站点变更而变化。

前台下载每批最多 100 章；Android 13+ 会请求通知权限。强制停止应用后不会自行批量下载，进入具体书籍详情后可继续本书队列。主动暂停需等待当前正在进行的网络请求返回。

程序按 AGPL-3.0-only 发布，依赖许可见 app/src/main/assets/licenses。书源开源许可不代表作品内容许可。
