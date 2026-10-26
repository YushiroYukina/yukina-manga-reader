# 在线版 0.1.3-preview 验证记录

这是独立在线版的验证范围。原本地版 v1.1／安卓 v1.1.1 的 Mac 或平板记录不作为本版实机通过依据。

## Windows／共享桌面逻辑

- 本机：Windows 11 x64（系统内部 build 26200）、Python 3.10.11、PySide6 6.12.0、PyMuPDF 1.28.2，使用原生 `windows` Qt 平台。
- 本地阅读器继承的 56 项自动回归，覆盖只读图书、压缩包／图片、目录、状态、计时、统计、沉浸布局、页距和翻页。
- 在线专用 35 项检查通过，覆盖六类接口、在线不写页面磁盘缓存、主动选目录、完成后离线重开、源停用后读取、断点续下、内容损坏校验、目录更新保留状态／进度／计时、切换缓存路径、清理已移出书库的下载、异步 GUI，以及长时间阅读图片地址过期刷新。
- 原生独立验收 `--online-validation NEW_DIR` 使用程序自己的合成漫画与本机 HTTP 服务，通过搜索 → 书库 → 在线翻页 → 沉浸浮层 → 主动下载 → 停用源 → 离线重开的界面流程。源码和成品使用相同验收程序；结果及截图写到新建隔离目录。
- Windows 打包发现错误：构建工具从环境搜索到不兼容的 ICU DLL，QtNetwork 启动失败。已从 Windows 包中排除这些 ICU 副本，使用 Windows 自带 ICU。修复后原生独立成品 27 项验收通过，正常启动、单实例复用和关闭保存亦通过。适配目标为 Windows 11 x64。

最终运行计数、打包结果与哈希另见 `BUILD_VALIDATION.json` 和发布目录校验文件；本页不将未执行检查写成通过。

## 0.1.3 预加载与画质

桌面回归 56 项、在线检查 35 项、Android 主机规则 39 项和生产 Java 协议 48 项通过。在线检查新增同页请求合并、其他页不受慢页锁阻塞、内存上限、预加载开关、重开不发网络请求、三档尺寸及原图不重压缩、MangaDex 原图／省流路径选择、错误响应不污染缓存。详细策略见 `ONLINE_PERFORMANCE.md`，真实计时见 `PERFORMANCE_VALIDATION.json`。

Android 9 模拟环境的首轮原生测试通过 21 项，覆盖三档画质尺寸、原图精确颜色与字节保留、关闭章节后的 RAM 复用等，之后因测试文档提供器权限配置失败中止。测试配置已修正并编译，但自动审批阻止了重新安装并启动带目录授权的测试包；完整原生流程没有记为通过。没有测试 Lenovo 平板 Android 14。

## 0.1.2 中文图片地址修复

已复现《水星领航员》首卷图片目录包含中文时的 `UnicodeEncodeError`，修复请求前的 UTF-8 地址转码，保留已有百分号转义，避免二次编码。修复前“搜索／目录可读”不代表正文和首图封面可用。源码及 Windows 独立成品均实际打开该书并生成第一页缩略封面；没有页面磁盘缓存。另测《葬送者芙莉莲》《孤独摇滚》及 MangaPill《One Piece》首章图片。启动后依次重试现有在线书籍缺失的封面，保留自定义封面。详细结果见 `UNICODE_URL_FIX_VALIDATION.json`。

27 项原生合成验收也已改为带中文和空格的页面目录，覆盖实际搜索、加入书库、封面、阅读及主动下载／离线重开。Android Java 增加地址和真实 HTTP 图片传输检查；本次没有 Android 或 Mac 实机。

## 真实网络来源

2026-10-25 小范围 MangaDex 探测：真实热门搜索返回 30 个结果，取得章节列表与 MangaDex@Home 页面清单，单页图像在内存解码为 1080×1551，读取 165739 字节。没有将该页写成漫画缓存或放入源码包。另有早期网络连接失败，加入有限重试后完整探测通过。这个结果只证明当时的一次链路，不保证所有作品、登录限制、网络、语言或未来接口。

新增默认漫画柜（中文）与 MangaPill（英文），真实搜索、章节、图片内存解码验证见 `COMMON_SOURCES_VALIDATION.json`。未将请求被拒绝或连接失败的 WeebCentral、包子漫画、漫画DB 等站点作为默认可用源。MangaDex 搜索现在会按章节语言筛选。网络测试仅反映检查时的来源状态。

Komga 与 Suwayomi 根据其公开接口／路由实现，通过本地模拟协议服务器检验数据解析与页面读取；没有可用的用户自建服务地址，因此没有把真实 Komga／Suwayomi 服务器及实际扩展兼容性写成通过。

## Android

- 包名 `cn.yukina.online`、versionCode 4、版本 0.1.3-preview；QA 包另为 `cn.yukina.online.qa`，可与原 `cn.migi.reader` 并存。
- 官方 SDK 34、便携 JDK 21 构建，APK v2/v3 签名验证；39 项继承主机规则检查通过。
- 生产 Java 适配器在 JVM 上执行的 48 项网络协议检查通过，使用与桌面检查相同的本地合成服务：六类搜索／章节／页面及内置书源合并、固定 HTML 解析和 LZ 字面量解码、中文字段、相对地址、CDN 地址过期刷新、稳定缓存标识、非法 URL 拒绝。生产 Java 代码另在主机 JVM 通过漫画柜、MangaPill 真实搜索、章节及单页图片头检查；使用与桌面相同的既有网络代理。发现移动版页面差异后统一请求标识，跳过菜单中的非网页链接。没有把主机代理设置写进 Android。上述检查不是 Android 原生 UI 或 SAF 实测。
- 本次没有连接联想平板。此前 Android 14 AVD 未能启动；此次 Android 9 模拟环境只完成上述 21 项原生子集，完整流程仍未通过。不安装系统内核驱动，不修改系统虚拟化配置。
- 已编译独立原生验收 APK，含可写 SAF 测试提供器和 `OnlineChecks`：准备验证系统授权下载路径、断点续下、校验修复、原生书库／沉浸 UI 与前台下载服务。本次只完成前 21 项子集，随后在 QA 文档提供器处中止；修正测试配置后的重装操作被自动审批拒绝。TF 卡写入、通知权限、后台下载行为和实际手势仍需连接设备验证。

执行方法（只允许独立 QA 包，不清空原阅读器）：

```powershell
python android/tools/build.py --instrumentation --qa
# 将 QA 应用与 QA tests APK 安装到明确指定设备，保持设备解锁
adb -s YOUR_SERIAL install -r android/dist/Migi-Android-QA.apk
adb -s YOUR_SERIAL install -r android/dist/Migi-Android-QA-tests.apk
# 运行本机合成服务并映射至设备
python tests/fixture_server.py --port 18951
adb -s YOUR_SERIAL reverse tcp:18951 tcp:18951
adb -s YOUR_SERIAL shell am instrument -w -e base http://127.0.0.1:18951 cn.yukina.online.qa.tests/cn.migi.reader.OnlineChecks
```

继承的 90 项本地原生检查可通过更新后的 `android/tools/device_verify.py --serial YOUR_SERIAL --physical` 运行，仅处理 QA 包。在线版没有自动选择设备、清空正式书库或覆盖本地版的脚本。

## Mac

共用桌面代码保留 Cocoa 原生窗口、快捷键、全屏、翻译、Retina 与触控板支持；独立应用标识 `cn.yukina.online.mac` 与数据目录已经配置。已有 Mac 构建脚本、arm64／ad-hoc 签名检查和同一套 `--online-validation` 验收入口。

当前电脑为 Windows，本次没有运行新的 Mac 原生窗口、构建 `.app`、签名或实机测试。Mac 交接步骤见 `macos/README.md`。这是明确待完成的目标机验收，不能由 Windows 自动测试替代。

## 保留与隔离

本次源代码在独立 `yukina-online` 目录开发，未推送或覆盖原仓库；正式本地阅读器、原用户书库和图书文件没有被迁移。测试使用原创合成页；源码包排除账号配置、书库、下载、工具链、签名密钥、截图调试日志和个人漫画。
