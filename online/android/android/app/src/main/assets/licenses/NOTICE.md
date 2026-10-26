# Copyright and third-party notices

yukina漫画阅读器 — Copyright (C) 2026 YushiroYukina.
Project source and releases: GNU AGPL version 3.0 only (AGPL-3.0-only). See LICENSE.

Desktop builds use PyMuPDF / MuPDF (Artifex and contributors), under AGPL-3.0 or a commercial license. This release uses the AGPL option. Qt / PySide6 / Shiboken (The Qt Company and contributors) retain their LGPL/GPL licenses. Dynamic Qt libraries remain separate. Python and PyInstaller retain their licenses and the PyInstaller bootloader exception.

Dependency sources and license references:
- https://github.com/pymupdf/PyMuPDF (version pinned in requirements.txt)
- https://mupdf.com/licensing/
- https://code.qt.io/pyside/pyside-setup.git/ and https://code.qt.io/qt/
- https://doc.qt.io/qtforpython-6/licenses.html
- https://www.python.org/psf/license/
- https://pyinstaller.org/en/stable/license.html

Application corresponding source and build scripts: https://github.com/YushiroYukina/yukina-manga-reader
Exact dependencies are in each platform's requirements files. Complete AGPL/GPL/LGPL texts accompany this release; dependency-specific notices remain applicable.


Archive decoder additions (2026-10-16):
- Desktop: unmodified 7-Zip 26.04 by Igor Pavlov, launched as a separate helper process. LGPL-2.1-or-later with the unRAR restriction and BSD notices; these components retain their original licenses and are not relicensed as AGPL. Source: https://github.com/ip7z/7zip/tree/26.04 ; official source archive https://github.com/ip7z/7zip/releases/download/26.04/7z2604-src.tar.xz . Readers can replace the helper under tools/sevenzip. Pinned download checksums are in tools/prepare_archives.py.
- Android: libarchive-android 1.1.6 (Google LLC / Hai Zhang; Apache-2.0), source https://github.com/zhanghai/libarchive-android/tree/v1.1.6 . It bundles libarchive, bzip2, XZ/liblzma, LZ4/xxHash, Zstandard and Mbed TLS, and uses Android zlib. The upstream tag records exact dependency commits via git submodules. Source can be obtained using git clone --branch v1.1.6 --recurse-submodules https://github.com/zhanghai/libarchive-android.git . The corresponding notice files are in licenses/archive and Android APK assets/licenses. Additional dependency licenses remain applicable.

## Independent Online Preview 0.1.0

Online adapters and UI additions are original AGPL-3.0-only code by this project. Komga (MIT), Suwayomi (MPL-2.0), and MangaDex public APIs are external services, not bundled servers or third-party extension code. Source protocol references are in docs/SOURCES.md. The optional JSON-java 20240303 JAR is downloaded only for JVM protocol checks and is not shipped in the Android APK or desktop application.

Common-source additions (0.1.3-preview): endpoints, selectors, and image metadata format were researched from Keiyoushi extensions-source, Copyright Keiyoushi contributors, Apache-2.0 (https://github.com/keiyoushi/extensions-source). The bounded LZ decoder is an original implementation of the LZ-string wire format described by pieroxy/lz-string, Copyright Pieroxy and contributors, MIT (https://github.com/pieroxy/lz-string). No upstream extension APK, remote JavaScript, or server is bundled or executed. These acknowledgments describe technical references; they do not grant rights to third-party manga content.

Android 在线版 0.1.4：包子漫畫.org / GoDa、ComicABC 和 MangaKatana 的公开端点及固定解析规则参考 Keiyoushi extensions-source（Apache-2.0）。适配器为本项目 Java 实现，不执行网页或扩展脚本。上游：https://github.com/keiyoushi/extensions-source
