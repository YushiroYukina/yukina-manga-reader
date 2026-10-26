# Mac 验证与打包交接

使用 MacBook Air M1、macOS 14+ 和原生 arm64 Python 3.12。此前本地阅读器在 macOS 26.5.1 的验证只作为继承基线；在线版新增功能必须按本页重新验证。

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r desktop/requirements.txt PyInstaller
.venv/bin/python desktop/tools/prepare_archives.py
.venv/bin/python desktop/app.py
```

应用名称为 yukina漫画阅读器·在线版。默认数据为 `~/Applications/YukinaOnline/online-data`，包标识为 `cn.yukina.online.mac`，不是旧 `Migi.app`；不打开旧版默认书库。

完整桌面逻辑检查：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python tests/test_online.py
cd desktop
QT_QPA_PLATFORM=offscreen ../.venv/bin/python -m unittest discover -s tests -v
cd ..
# Cocoa 原生窗口 + 本地 HTTP 合成漫画 + 下载后离线重开
.venv/bin/python desktop/app.py --online-validation work/mac-source-001
.venv/bin/python macos/build_macos.py
./dist/YukinaOnline.app/Contents/MacOS/YukinaOnline --online-validation work/mac-app-001
```

每次验证使用新的目录。测试目录中保存 `online-validation.json` 与界面截图，不读取日常书库。需要人工核对：日漫右到左、横向翻页动画、原生全屏／沉浸浮层、触控板、外接屏、实际书源与外置磁盘缓存。新在线版尚未在本次 Windows 工作中完成 Mac 原生运行或打包，不能把 Windows 通过结果作为 Mac 通过结果。

构建脚本生成独立 `YukinaOnline.app`，验证 arm64 Mach-O 与 ad-hoc 签名，再通过 `ditto` 压缩。无需改动旧阅读器；ad-hoc 签名不等同 Apple 公证。更新反馈请返回本项目源码及 `work/mac-*/online-validation.json`，不要包含账号配置或个人图书。
