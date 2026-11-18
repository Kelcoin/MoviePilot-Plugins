# MoviePilot-Plugins

MoviePilot 第三方插件仓库

## Emby 302 多服务器反向代理

- [V3 插件](plugins.v3/embyreverseproxymulti)
- [V2 插件](plugins.v2/embyreverseproxymulti)

Emby 302 多服务器反向代理，支持多个 Emby 服务器和监听端口，自动代理 HTTP 链接并跳转最终地址，支持外部播放器调用。

配置格式：

```text
http://emby-a:8096 => 0.0.0.0:8099
http://emby-b:8096 => 0.0.0.0:8100
```

## 神医媒体文件同步删除（多服务器）

- [V3 插件](plugins.v3/samediasyncdelmulti)
- [V2 插件](plugins.v2/samediasyncdelmulti)

通过神医助手（StrmAssistant）的媒体深度删除通知，同步删除 MoviePilot 转移记录中记录的源文件与下载任务，支持 115 网盘、123 网盘与本地文件。

本仓库版本同步自 [DDSRem-Dev/MoviePilot-Plugins](https://github.com/DDSRem-Dev/MoviePilot-Plugins)，V2 版本为 1.1.0、V3 版本为 3.1.0，包含以下改进：

- 支持多选 Emby 媒体服务器，缺少剧集 TMDB ID 时只向发出通知的服务器查询。
- Emby 通知目标以 JSON 报文直接投递时无法解析，事件到不了插件；
- 深度删除下发的路径是媒体目录且带 Windows 反斜杠，导致路径映射与转移记录无法匹配；
- 深度删除事件名带命名空间前缀（如 `strmassistant.deep.delete`）时被当成非深度删除事件跳过。
- V3 版本写死宿主 `u115` 存储，只登录了 115网盘Plus 插件存储时无法删除（现按「自动探测」依次尝试，可在插件设置中指定）。

在插件市场中搜索「神医媒体文件同步删除（多服务器）」即可安装。该版本使用独立插件 ID `SaMediaSyncDelMulti`。
从 `SaMediaSyncDel` 迁移时，请先停用旧插件，在新插件中重新配置路径映射和其他设置，并把 Emby 通知 URL 的插件 ID 改为 `SaMediaSyncDelMulti`。旧插件的配置与历史不会自动迁移。

Emby 通知需指向插件端点（`<API_TOKEN>` 为 MoviePilot 的 API 令牌），并勾选「媒体深度删除」：

```text
http://<MoviePilot 地址>:3001/api/v1/plugin/SaMediaSyncDelMulti/emby_webhook?apikey=<API_TOKEN>
```

多台 Emby 同时使用时，在插件的「媒体服务器」中选中每台服务器，并分别配置通知 URL。
`server` 的值填写 MoviePilot 中的媒体服务器配置名称，含中文、空格等字符时需进行 URL 编码。
例如，MoviePilot 中名为 `Emby-A` 和 `Emby-B` 的两台服务器分别使用：

```text
http://<MoviePilot 地址>:3001/api/v1/plugin/SaMediaSyncDelMulti/emby_webhook?apikey=<API_TOKEN>&server=Emby-A
http://<MoviePilot 地址>:3001/api/v1/plugin/SaMediaSyncDelMulti/emby_webhook?apikey=<API_TOKEN>&server=Emby-B
```

只选一台时，原有 URL 可继续使用。多选后，缺少 `server` 或名称不在插件所选列表里的深度删除通知会被拒绝。
所有服务器共用插件的路径映射。如果各台 Emby 使用不同的目录，请配置相应的路径前缀；同一个前缀只能对应一个删除目标。

## 许可证

此仓库根据 GNU General Public License v3.0 许可证进行许可，详见 [LICENSE](LICENSE)。
