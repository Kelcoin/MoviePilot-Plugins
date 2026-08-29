# MoviePilot-Plugins

MoviePilot 第三方插件仓库

## Emby 302 反向代理

- [V3 插件](plugins.v3/embyreverseproxy)
- [V2 插件](plugins.v2/embyreverseproxy)

Emby 302 反向代理，支持多个 Emby 服务器和监听端口，自动代理 HTTP 链接并跳转最终地址，支持外部播放器调用。

配置格式：

```text
http://emby-a:8096 => 0.0.0.0:8099
http://emby-b:8096 => 0.0.0.0:8100
```

## 许可证

此仓库根据 GNU General Public License v3.0 许可证进行许可，详见 [LICENSE](LICENSE)。
