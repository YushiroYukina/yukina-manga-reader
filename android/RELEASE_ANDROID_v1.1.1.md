# yukina漫画阅读器 安卓版 v1.1.1

这是一次**仅针对 Android 的独立小版本更新**。Windows 与 macOS 版本没有随本次更新。

## 更新内容

- 优化手动拖动翻页时的页面绘制与预读复用；翻页页间隙保持不透明，减少相邻页之间透出底图。
- 平移与覆盖动画中，新页进入和旧页退出同步进行，方向相反。
- 将翻页动画选择移至“阅读外观 → 翻页动画”二级页面，页间距、阅读方向和主题继续在外观页设置。
- 优化多卷书籍详情页，提供阅读摘要、分卷筛选及更集中的分卷/整书操作菜单。
- 阅读原书仍采用授权位置按需读取；不复制原书，也不生成页面磁盘缓存。

## 兼容与验证

- 面向 Android 平板与手机，最低 Android 8.0（API 26）。主要实机为联想小新 Pad Pro 12.7（骁龙 870，Android 14）。
- 本次源码的 39 项主机检查及该平板上的 90 项真机检查通过。现有应用使用原签名覆盖安装，versionCode 为 5；升级时原有书库保留。
- 性能数据来自单台平板、单本 TF 卡 EPUB 的有限横屏样本。书籍翻页效果仍有慢帧，尾部耗时有波动；此次不宣称已完全消除卡顿，也不代表所有设备和图书格式。Android 10 以下仅保留兼容绘制路径，未在本次实机验证。

## 下载

- [Android 安装包 APK](https://github.com/YushiroYukina/yukina-manga-reader/releases/download/android-v1.1.1/yukina-reader-android-v1.1.1.apk)
- [Android 源码（AGPL-3.0-only）](https://github.com/YushiroYukina/yukina-manga-reader/releases/download/android-v1.1.1/yukina-android-source-v1.1.1.zip)
- [SHA-256 校验文件](https://github.com/YushiroYukina/yukina-manga-reader/releases/download/android-v1.1.1/SHA256SUMS.txt)

侧载安装前请确认下载来源；如从旧版升级，请直接覆盖安装，不要先卸载，以保留应用内书库数据。

反馈问题时请附设备型号、Android 版本、书籍格式及复现步骤。
