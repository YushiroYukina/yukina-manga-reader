# 书源协议、上游与认证

所有接入代码均为本项目新写的适配器，不包含第三方站点解析脚本。支持接口类型：

| 类型 | 地址 | 认证字段 | 说明 |
|---|---|---|---|
| mangadex | `https://api.mangadex.org` | 可选访问令牌 | 语言 `zh` 含 `zh-hk`；可设 `ja`、`en` 等；默认 safe / suggestive，不请求外部跳转章节 |
| manhuagui | `https://www.manhuagui.com` | 无需账号 | 漫画柜中文，搜索／目录／公开图片清单，跳过不可读章节；不执行网页 JavaScript |
| mangapill | `https://mangapill.com` | 无需账号 | 英文漫画，搜索／章节／图片，使用图片所需 Referer |
| komga | 您的 Komga 根地址 | API Key 或用户名／密码 | `/api/v1/series` → books → pages；需页面流式阅读权限 |
| suwayomi | 您的 Suwayomi 根地址 | 用户名／密码或服务端支持的令牌 | `/api/v1/source/list` 选扩展；每个扩展可作为一个独立书源 |
| catalog | 完整目录 JSON 地址 | 可选同源认证 | 静态 JSON＋图片，适合开源、自建目录或合成测试 |

添加／编辑时认证只保存在线版自己的配置。Windows／Mac 配置文件尝试限制为当前用户读写；Android 配置位于应用私有目录。认证不是跨设备同步；不要公开分享含认证的手工配置。桌面端导出与三端导入书源包均剔除认证字段，须在导入后自行填写。

请求使用默认 TLS 证书验证；仅接受 HTTP(S) URL，拒绝 URL 内嵌账号；跨域跳转不转发认证，HTTPS 不降级跳至 HTTP。认证只发往当前配置根地址同源，MangaDex 图像 CDN 不附加 API 认证。处理 429 及 Retry-After，限速串行下载。不提供绕过验证的实现。

## 可导入的书源包

`sources/common-presets.json` 是三端一致的默认书源包：漫画柜、MangaDex、MangaPill。更新版本首次启动时按 ID 补齐，不覆盖现有名称、认证、开关、缓存路径和阅读记录。迁移完成后移除书源不会自动重加，可手动导入该文件恢复。网页结构和网络可达性会变化，当前验证结果在 `docs/COMMON_SOURCES_VALIDATION.json`。

MangaDex 搜索按选择的章节语言过滤；中文包括简体和繁体。漫画柜主站请求间隔至少 3 秒，图片间隔至少 1 秒；图片签名失效时只重新读取一次公开章节清单。图片只在内存验证，主动下载才会写入指定缓存。

```json
{
  "version": 1,
  "sources": [
    {"id":"my-komga","name":"我的 Komga","type":"komga","base_url":"https://your-server.example","enabled":true},
    {"id":"my-suwa-zh","name":"我的中文扩展","type":"suwayomi","base_url":"https://your-suwa.example","source_id":"1234567890123456789","enabled":true}
  ]
}
```

示例域名只是占位符，不是可用书源。Suwayomi ID 应从自己的服务端实际列表选择，按字符串保留，避免大整数丢失精度。书源包可通过本地文件或链接导入，一次最多 100 个。重复 ID 跳过，不覆盖现有认证。目录更新保留旧章节进度、状态、计时和缓存，即使某章从上游暂时消失。

## Yukina JSON 目录

```json
{"version":1,"books":[{"id":"original-comic","title":"原创漫画","cover":"cover.png","chapters":[{"id":"chapter-1","title":"第 1 话","pages":["pages/001.png","pages/002.png"]}]}]}
```

图片和封面地址相对目录 JSON 解析，也可用完整 HTTP(S) URL。作品／章节 ID 应稳定且唯一；标题变更不应改 ID。页序完全使用 `pages` 数组顺序。JSON 上限 8 MiB，单张图片上限 32 MiB，单章节最多 10000 页；图片解码会限制纹理尺寸。阅读时不创建页面磁盘缓存；章节清单与书库元数据会持久保存。

随源码的 `tests/fixture_server.py` 提供原创合成测试图，不含商业漫画。运行后可添加 `http://127.0.0.1:18951/catalog.json`；Android 模拟器使用 `http://10.0.2.2:18951/catalog.json`。这仅是测试目录，不是公开网络书源。

## 接口依据（2026-10-25 查阅）

- MangaDex 官方 API 文档：<https://api.mangadex.org/docs/>；真实搜索已独立探测，图片链路情况见验证记录。
- 漫画柜参考：[Keiyoushi Manhuagui 适配器](https://github.com/keiyoushi/extensions-source/tree/main/src/zh/manhuagui)，Apache-2.0。
- MangaPill 参考：[Keiyoushi MangaPill 适配器](https://github.com/keiyoushi/extensions-source/tree/main/src/en/mangapill)，Apache-2.0。
- 图片清单压缩格式：[pieroxy/lz-string](https://github.com/pieroxy/lz-string)，MIT；只解码字面量数据，不运行 `eval` 或远程代码。
- Komga MIT 项目：<https://github.com/gotson/komga>；公开 API：<https://komga.org/docs/openapi/komga-api/>，支持 Basic 和 X-API-Key。
- Suwayomi MPL-2.0 项目：<https://github.com/Suwayomi/Suwayomi-Server>；REST 路由源码：`server/src/main/kotlin/suwayomi/tachidesk/manga/MangaAPI.kt`，解析遵循其 `SourceController` 与 `ChapterDataClass`。REST 接口未来变更可能需要适配。

本地版与在线版没有共享运行目录。源码／书源适配器许可不赋予第三方漫画版权；可访问性、作品授权和服务器维护由各来源决定。
