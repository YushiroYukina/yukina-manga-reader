# License update

The maintainer selected AGPL-3.0-only for source and releases. See LICENSE, NOTICE.md and licenses/ in the repository root. Historical preparation notes below do not override this decision.

# 许可状态

作者尚未为原创项目代码选定发布许可证。本次准备不新增 MIT、GPL 或其他许可证授权。先上传私有仓库，再决定是否公开及如何授权。

Windows 依赖 PyMuPDF/MuPDF：采用 AGPL 与商业双重许可，不能直接认为完整项目可无条件按 MIT 分发。PySide6/Qt 也有各自许可条款，分发时须保留对应声明并检查具体组件。
Android 使用 Android 平台 API 和官方构建工具，未把 SDK/JDK 二进制随源码再分发；下载与使用工具遵守厂商许可。
Mac 1.0.1 已整合为独立实现，仍使用 Python/Qt/PyMuPDF 依赖；详细待核对事项见 [Mac 许可说明](../macos/docs/LICENSING.md)。人工生成的纯色测试资料不含用户图书。

官方资料：
- https://pymupdf.io/licensing
- https://github.com/pymupdf/PyMuPDF
- https://doc.qt.io/qtforpython-6/licenses.html

本文仅列出依赖与待决定事项，不替作者作许可证选择。
