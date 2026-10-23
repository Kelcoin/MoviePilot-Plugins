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

## 神医媒体文件同步删除

- [V3 插件](plugins.v3/samediasyncdel)
- [V2 插件](plugins.v2/samediasyncdel)

通过神医助手（StrmAssistant）的媒体深度删除通知，同步删除 MoviePilot 转移记录中记录的源文件与下载任务，支持 115 网盘、123 网盘与本地文件。

本仓库版本同步自 [DDSRem-Dev/MoviePilot-Plugins](https://github.com/DDSRem-Dev/MoviePilot-Plugins)，V2 版本为 1.0.10、V3 版本为 3.0.1，修正以下问题：

- Emby 通知目标以 JSON 报文直接投递时无法解析，事件到不了插件；
- 深度删除下发的路径是媒体目录且带 Windows 反斜杠，导致路径映射与转移记录无法匹配；
- 深度删除事件名带命名空间前缀（如 `strmassistant.deep.delete`）时被当成非深度删除事件跳过。

Emby 通知需指向插件端点（`<API_TOKEN>` 为 MoviePilot 的 API 令牌），并勾选「媒体深度删除」：

```text
http://<MoviePilot 地址>:3001/api/v1/plugin/SaMediaSyncDel/emby_webhook?apikey=<API_TOKEN>
```

## 许可证

此仓库根据 GNU General Public License v3.0 许可证进行许可，详见 [LICENSE](LICENSE)。
