# yukina漫画阅读器 · Android 在线版 0.1.4 源码

本包仅包含 Android 更新所需的源码、构建脚本、许可及合成测试素材。应用源码与构建入口位于 android/，详见 android/README.md。Windows 与 Mac 不在本源码包内。

在 Windows 上进入 android 目录后，使用 Python 3.10+ 执行 python tools/bootstrap.py，再执行 python tools/build.py；也可用 YUKINA_ANDROID_TOOLS 指向已有工具目录。首次构建会准备官方 SDK、JDK 及归档解码库。密钥不随包分发，重新生成密钥的构建不能覆盖现有在线版。

从本包根目录运行 python tools/verify_source.py 检查源码清单。生产 Java 协议测试入口 tools/test_android_protocol.py 另需 pip install PySide6==6.12.0，用于生成本机合成图片测试；测试工具会校验 JSON-java 测试依赖哈希。测试素材不含实际漫画。

本轮 Android 15 联想 TB371FC 实机结果及网络限制见 docs/ANDROID_UPDATE.md 与 docs/ANDROID_UPDATE_VALIDATION.json。程序 AGPL-3.0-only；第三方许可见 LICENSE、NOTICE.md、licenses 与 android/app/src/main/assets/licenses。
