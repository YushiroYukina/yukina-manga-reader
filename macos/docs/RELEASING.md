# GitHub 发布准备

1. 先处理 LICENSING.md 的待确认事项，填写项目作者、许可证和第三方声明。
2. 在独立文件夹解包，校验完整性：`python3 scripts/verify_source.py`。
3. 使用原生 arm64 Python 3.12 创建虚拟环境并安装固定依赖。
4. 运行 `scripts/test_macos.py`，再用新目录执行 Cocoa 独立检查。保存必要且已脱敏的结果。
5. 运行 `scripts/build_macos.py`；从生成的 ZIP 实际解包，再核对签名、启动、重复启动、中文文件对话框、三格式和保存恢复。
6. 发布前按自己的方案处理签名／公证以及依赖许可；项目自用 ad-hoc 签名不代表 Apple 已公证。
7. 创建自己的 GitHub 空仓库，将本目录内容作为仓库根目录提交。不要提交 `.venv`、`work`、`dist`、个人图书或书库。
8. 使用版本 `v1.0.1` 和 `.github/RELEASE_TEMPLATE.md` 准备 Release；二进制只在完成发行许可核对后附加。不要将仓库生成的源码 ZIP 误标为独立应用。

本包没有绑定任何个人 Git remote，没有创建 GitHub 仓库、推送提交或发布 Release。未添加未经验证的云端构建工作流；本机原生验证不能由未运行的 CI 代替。
