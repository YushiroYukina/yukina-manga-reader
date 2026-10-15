# 右页 · MIGI

面向日漫的本地阅读器，默认右到左阅读，支持 PDF、EPUB、MOBI。只引用原文件，不复制图书、不缓存阅读页面；允许清理封面缩略图。

| 目录 | 内容 | 验证状态 |
| --- | --- | --- |
| desktop/ | Windows Python / PySide6 / PyMuPDF 阅读器 | 既有 Windows 功能基线；本次准备包另做静态与测试验证 |
| android/ | Android Java 原生平板阅读器，API 26+ / target 34 | 最近已有 24 项主机与 49 项真机检查通过 |
| macos/ | Apple Silicon 构建交接模板 | 未收到 Mac 后续源码；未作 Mac 原生验证 |
| docs/ | 上传、许可、验证说明 | 上传前先阅读 |

功能包括独立书库、批量导入与多卷合辑、阅读状态、封面管理、沉浸阅读、主题、翻页效果和阅读时长统计。Android 另支持 TF 卡 SAF 授权、父目录批量合辑与实时跟手翻页；格式支持和计时规则存在平台差异，详见各端 README。

## 从源码启动 Windows 端

```powershell
cd desktop
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

测试：在 desktop 目录运行 `.venv\Scripts\python.exe -m unittest discover -s tests -v`。
打包需要另装 PyInstaller，然后执行 `python -m PyInstaller --noconfirm Migi.spec`。start.bat 用于启动打包后的程序，并非源码启动器。

Android 使用 Windows 便携工具链构建，见 [安卓说明](android/README.md)。Mac 见 [交接说明](macos/README.md)。

## 准备上传

先读 [GitHub 新手指南](docs/GITHUB_START.md)，运行 `python tools/verify_source.py` 检查源码包完整性。此目录是独立整理的源码快照，与原开发目录不自动同步；后续修改需要更新到该仓库后提交。

未包含个人图书、书库、封面缓存、阅读截图、SDK/JDK、虚拟环境、安装包或原开发签名。只有 android/tests/assets 中三份人工生成的测试图书属于测试资料。

尚未替作者选择开源许可证；不要直接将本项目视为 MIT。依赖和后续许可选择见 [许可说明](docs/LICENSING.md)。
