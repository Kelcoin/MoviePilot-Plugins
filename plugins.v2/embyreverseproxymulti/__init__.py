from threading import Thread
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

from uvicorn import Config, Server

from app.log import logger
from app.plugins import _PluginBase

from .external_players import EXTERNAL_PLAYERS
from .proxy_app import create_app


PIN_RULES_SEP = " => "
SERVERS_SEP = " => "


def _parse_servers(raw: str) -> List[Tuple[str, str, int]]:
    """
    解析多行 Emby 服务器与监听配置

    :param raw (str): 每行「Emby地址 => [监听地址:]端口」

    :return List: 合法配置列表，元素为 (Emby地址, 监听地址, 监听端口)
    """
    result: List[Tuple[str, str, int]] = []
    for line_number, line in enumerate((raw or "").strip().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        if SERVERS_SEP not in line:
            logger.warning("Emby服务器配置第 %s 行格式错误，已忽略", line_number)
            continue
        emby_host, listener = (part.strip() for part in line.split(SERVERS_SEP, 1))
        if not emby_host.startswith(("http://", "https://")):
            emby_host = "http://" + emby_host
        try:
            parsed = urlparse(emby_host)
            _ = parsed.port
            valid_emby = bool(parsed.hostname) and not parsed.username and not parsed.password
        except ValueError:
            valid_emby = False
        if not valid_emby or any(char.isspace() for char in emby_host):
            logger.warning("Emby服务器配置第 %s 行地址无效，已忽略", line_number)
            continue

        listener_host = "0.0.0.0"
        port_text = listener
        if listener.startswith("["):
            closing = listener.find("]")
            if closing < 0 or closing + 1 >= len(listener) or listener[closing + 1] != ":":
                port_text = ""
            else:
                listener_host = listener[1:closing]
                port_text = listener[closing + 2 :]
        elif ":" in listener:
            listener_host, port_text = listener.rsplit(":", 1)
            listener_host = listener_host.strip()
        try:
            port = int(port_text)
        except (TypeError, ValueError):
            port = 0
        if not listener_host or any(char.isspace() for char in listener_host) or not 1 <= port <= 65535:
            logger.warning("Emby服务器配置第 %s 行监听地址或端口无效，已忽略", line_number)
            continue
        result.append((emby_host.rstrip("/"), listener_host, port))
    return result


def _parse_pin_rules(raw: str) -> List[Tuple[str, str]]:
    """
    解析顶置路径规则字符串为 (路径前缀, 目标URL) 列表

    :param raw: 多行文本，每行「路径前缀 => 目标URL」（用 " => " 分隔，两侧可含空格）
    :return: 合法规则列表；非法行忽略并打日志
    """
    result: List[Tuple[str, str]] = []
    for line in (raw or "").strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if PIN_RULES_SEP not in line:
            logger.warning(
                '顶置规则格式错误，已忽略（需用 " => " 分隔路径前缀与目标URL）: %s',
                line,
            )
            continue
        parts = line.split(PIN_RULES_SEP, 1)
        path_prefix = parts[0].strip()
        target_url = parts[1].strip()
        if not path_prefix or not target_url:
            logger.warning("顶置规则路径或目标为空，已忽略: %s", line)
            continue
        if not target_url.startswith(("http://", "https://")):
            logger.warning(
                "顶置规则目标需以 http:// 或 https:// 开头，已忽略: %s => %s",
                path_prefix,
                target_url,
            )
            continue
        result.append((path_prefix, target_url))
    return result


class EmbyReverseProxyMulti(_PluginBase):
    """
    Emby 302 多服务器反向代理

    Attributes:
        _servers_raw: 多服务器原始配置
        _server_configs: 已解析的服务器配置
        _media_source_path_prefixes_raw: 媒体源隐藏前缀原始配置
        _media_source_path_prefixes: 已拆分的媒体源隐藏前缀
    """

    plugin_name = "Emby 302 多服务器反向代理"
    plugin_desc = (
        "Emby 302 多服务器反向代理，自动代理 HTTP 链接，跳转最终地址，支持外部播放器调用。"
    )
    plugin_icon = "https://raw.githubusercontent.com/jxxghp/MoviePilot-Plugins/refs/heads/main/icons/Emby_A.png"
    plugin_version = "0.2.7"
    plugin_author = "Kelcoin"
    author_url = "https://github.com/Kelcoin"
    plugin_config_prefix = "embyreverseproxymulti_"
    plugin_order = 20
    auth_level = 1

    _enabled = False
    _emby_host = ""
    _servers_raw = ""
    _server_configs: List[Tuple[str, str, int]] = []
    _host = "0.0.0.0"
    _port = 8099
    _pin_rules: List[Tuple[str, str]] = []
    _pin_rules_raw = ""
    _media_source_path_prefixes_raw = ""
    _media_source_path_prefixes: List[str] = []
    _external_player_url = False
    _external_player_list: List[str] = []
    _server = None
    _thread = None
    _proxy_servers: List[Server] = []
    _proxy_threads: List[Thread] = []

    def init_plugin(self, config: Dict[str, Any] | None = None) -> None:
        """
        初始化插件：解析配置，启用时在独立线程启动 uvicorn，否则停止服务

        :param config (Dict): 插件配置字典
        """
        if config:
            self._enabled = config.get("enabled", False)
            self._servers_raw = (config.get("servers") or "").strip()
            self._emby_host = (config.get("emby_host") or "").strip()
            self._host = (config.get("host") or "0.0.0.0").strip() or "0.0.0.0"
            try:
                self._port = int(config.get("port") or 8099)
            except (TypeError, ValueError):
                self._port = 8099
            if self._servers_raw:
                self._server_configs = _parse_servers(self._servers_raw)
            elif self._emby_host:
                self._servers_raw = f"{self._emby_host} => {self._host}:{self._port}"
                self._server_configs = _parse_servers(self._servers_raw)
            else:
                self._server_configs = []
            if self._server_configs:
                self._emby_host, self._host, self._port = self._server_configs[0]
            self._pin_rules_raw = (config.get("pin_rules") or "").strip()
            self._pin_rules = _parse_pin_rules(self._pin_rules_raw)
            self._media_source_path_prefixes_raw = (
                config.get("media_source_path_prefixes") or ""
            ).strip()
            self._media_source_path_prefixes = [
                line.strip()
                for line in self._media_source_path_prefixes_raw.splitlines()
                if line.strip()
            ]
            self._external_player_url = config.get("external_player_url", False)
            self._external_player_list = config.get("external_player_list") or []
            self._update_config()

        self.stop_service()

        if self._enabled and self._server_configs:
            for emby_host, host, port in self._server_configs:
                try:
                    app = create_app(
                        emby_host,
                        pin_rules=self._pin_rules,
                        media_source_path_prefixes=self._media_source_path_prefixes,
                        external_player_url=self._external_player_url,
                        external_player_list=self._external_player_list,
                    )
                    uv_config = Config(app=app, host=host, port=port, log_config=None)
                    server = Server(uv_config)
                    thread = Thread(target=server.run, daemon=True)
                    self._proxy_servers.append(server)
                    self._proxy_threads.append(thread)
                    thread.start()
                    logger.info(
                        "EmbyReverseProxyMulti 代理已启动: %s:%s -> %s",
                        host,
                        port,
                        emby_host,
                    )
                except Exception as e:
                    logger.error("EmbyReverseProxyMulti 启动失败: %s", e, exc_info=True)
            self._server = self._proxy_servers[0] if self._proxy_servers else None
            self._thread = self._proxy_threads[0] if self._proxy_threads else None
            if not self._proxy_servers:
                logger.warning("EmbyReverseProxyMulti 没有可启动的有效配置")
        elif self._enabled:
            logger.warning("EmbyReverseProxyMulti 已启用但未配置有效 Emby 地址，代理未启动")

    def _update_config(self) -> None:
        """
        将当前配置写回插件配置存储
        """
        self.update_config(
            {
                "enabled": self._enabled,
                "servers": self._servers_raw,
                "emby_host": self._emby_host,
                "host": self._host,
                "port": self._port,
                "pin_rules": self._pin_rules_raw,
                "media_source_path_prefixes": self._media_source_path_prefixes_raw,
                "external_player_url": self._external_player_url,
                "external_player_list": self._external_player_list,
            }
        )

    def stop_service(self) -> None:
        """
        停止代理服务：设置 server.should_exit 并等待线程结束
        """
        if self._proxy_servers:
            try:
                for server in self._proxy_servers:
                    server.should_exit = True
                for thread in self._proxy_threads:
                    if thread.is_alive():
                        thread.join(timeout=5.0)
                logger.info("EmbyReverseProxyMulti 代理已停止")
            except Exception as e:
                logger.error("EmbyReverseProxyMulti 停止异常: %s", e, exc_info=True)
            finally:
                self._proxy_servers.clear()
                self._proxy_threads.clear()
                self._server = None
                self._thread = None

    def get_state(self) -> bool:
        """
        返回插件启用状态

        :return bool: True 表示插件已启用
        """
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """
        返回插件远程命令列表，本插件无远程命令

        :return List: 插件远程命令列表
        """
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        """
        返回插件 API 端点列表，本插件无自定义 API

        :return List: 空列表
        """
        return []

    def get_page(self) -> List[dict]:
        """
        返回插件数据页面配置，本插件无数据页面

        :return List: 插件数据页面配置
        """
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面

        :return Tuple: (页面配置列表, 表单默认值字典)
        """
        player_select_items = [
            {"title": info["name"], "value": key}
            for key, info in EXTERNAL_PLAYERS.items()
        ]
        return [
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "enabled",
                                    "label": "启用插件",
                                    "hint": "开启后将在独立端口运行 Emby 反向代理",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "external_player_url",
                                    "label": "外部播放器",
                                    "hint": "在 Emby 客户端中显示「使用外部播放器打开」按钮",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VTextarea",
                                "props": {
                                    "model": "media_source_path_prefixes",
                                    "label": "媒体源隐藏前缀（每行一个）",
                                    "rows": 3,
                                    "placeholder": "http://host:3000/api/.../redirect_url",
                                    "hint": (
                                        "留空关闭。匹配后优先展示并解码 file_name 参数，"
                                        "否则展示并解码剩余路径；不影响播放和探测"
                                    ),
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                ],
            },
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VTextarea",
                                "props": {
                                    "model": "servers",
                                    "label": "Emby 服务器与监听配置",
                                    "rows": 4,
                                    "placeholder": "每行一条：Emby地址 => [监听地址:]端口\nhttp://192.168.1.100:8096 => 0.0.0.0:8099",
                                    "hint": "支持多个 Emby；监听地址可省略，默认 0.0.0.0。旧版单服务器配置会自动转换",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                ],
            },
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VSelect",
                                "props": {
                                    "model": "external_player_list",
                                    "label": "外部播放器列表",
                                    "items": player_select_items,
                                    "multiple": True,
                                    "chips": True,
                                    "clearable": True,
                                    "hint": "选择要显示的外部播放器，留空则显示全部",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                ],
            },
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VTextarea",
                                "props": {
                                    "model": "pin_rules",
                                    "label": "顶置路径规则",
                                    "rows": 4,
                                    "placeholder": "每行一条：路径前缀 => 目标URL",
                                    "hint": "高级配置：不理解规则含义请勿配置（建议留空）。每行一条，格式：路径前缀 => 目标 URL；匹配到前缀后将路径替换为目标 URL 并返回 302。示例：/strm/cd2 => http://192.168.31.99:4567/d",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                ],
            },
        ], {
            "enabled": False,
            "servers": "",
            "emby_host": "",
            "host": "0.0.0.0",
            "port": 8099,
            "pin_rules": "",
            "media_source_path_prefixes": "",
            "external_player_url": False,
            "external_player_list": [],
        }
