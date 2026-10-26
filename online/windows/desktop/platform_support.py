"""macOS resources and user-owned storage; never write into a signed bundle."""
import os
import sys
from pathlib import Path

FONT_FAMILY = 'PingFang SC' if sys.platform == 'darwin' else 'Microsoft YaHei UI'
RESOURCE_ROOT = Path(__file__).resolve().parent

def bundle_contains(path):
    return any(p.suffix.lower() == '.app' for p in (Path(path).resolve(), *Path(path).resolve().parents))

def runtime_root():
    override = os.environ.get('YUKINA_ONLINE_DATA_ROOT')
    if override:
        root = Path(override).expanduser().resolve()
    elif sys.platform == 'darwin':
        # A fixed location survives moving/updating the app and Finder App Translocation.
        root = Path.home() / 'Applications' / 'YukinaOnline' / 'online-data'
    else:
        root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else RESOURCE_ROOT
        root = root / 'online-data'
    if sys.platform == 'darwin' and bundle_contains(root):
        raise ValueError('书库与缓存目录不能位于 .app 内')
    return root

MULTI_FILE_TITLE = '批量选择图书（Command / Shift 多选）' if sys.platform == 'darwin' else '批量选择图书（Ctrl / Shift 多选）'

def restore_after_native_dialog(owner):
    """Cocoa's modal panel may leave its owning window ordered out on return."""
    if sys.platform != 'darwin': return
    from PySide6.QtCore import QTimer
    window=owner.window()
    def restore():
        if not window.isVisible(): window.show()
        window.raise_(); window.activateWindow()
        if window.windowHandle(): window.windowHandle().requestActivate()
    restore()
    QTimer.singleShot(0,restore)


def install_chinese_translation(app):
    from PySide6.QtCore import QLocale,QTranslator,QLibraryInfo
    QLocale.setDefault(QLocale('zh_CN'))
    translator=QTranslator(app)
    paths=[RESOURCE_ROOT/'translations',Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))]
    for path in paths:
        if translator.load('qtbase_zh_CN',str(path)):
            app.installTranslator(translator)
            app._migi_chinese_translator=translator
            return True
    raise RuntimeError('缺少 Qt 简体中文翻译资源')
