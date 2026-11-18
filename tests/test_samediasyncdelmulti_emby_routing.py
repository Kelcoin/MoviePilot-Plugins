import ast
import asyncio
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional, Tuple
from unittest.mock import MagicMock, Mock


class EmbyRoutingTest(unittest.TestCase):
    """验证两个发布线的 Webhook 路由，使用替身隔离 MoviePilot 服务"""

    def _load_plugin(self, version: int) -> Tuple[Any, Dict[str, Any], Mock]:
        path = Path(__file__).resolve().parents[1] / f"plugins.v{version}/samediasyncdelmulti/__init__.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        plugin = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        # 仅替换宿主依赖，直接执行插件类中的路由、事件与查询逻辑
        tree.body = ast.parse("from __future__ import annotations").body + [plugin]
        helper = Mock()
        helper.get_services.return_value = {}
        response = MagicMock()
        response.__enter__.return_value.json.return_value = {"ProviderIds": {"Tmdb": "42"}}
        request_utils = Mock()
        request_utils.return_value.get_res.return_value = response
        namespace = dict(
            _PluginBase=object, asyncio=asyncio, json=json, Path=Path, logger=Mock(),
            eventmanager=Mock(register=lambda *_: lambda fn: fn),
            EventType=SimpleNamespace(WebhookMessage="webhook", DownloadFileDeleted="download"),
            schemas=SimpleNamespace(
                Response=lambda **fields: SimpleNamespace(**{"message": "", **fields}),
                WebhookEventInfo=lambda **fields: SimpleNamespace(**{
                    "item_name": None, "item_id": None, "media_id": None, "media_source": None, **fields
                }),
            ),
            MediaSource=SimpleNamespace(TMDB="tmdb"), settings=SimpleNamespace(API_TOKEN="token"),
            MediaServerHelper=lambda: helper, DownloaderHelper=lambda: SimpleNamespace(get_services=lambda: {}),
            StorageChain=Mock(), TransferChain=Mock(), TransferHistoryOper=Mock(), DownloadHistoryOper=Mock(),
            RequestUtils=request_utils,
        )
        exec(compile(tree, str(path), "exec"), namespace)
        instance = namespace["SaMediaSyncDelMulti"]()
        instance.update_config = Mock()
        instance._SaMediaSyncDelMulti__sync_del = Mock()
        return instance, namespace, helper

    def test_routes_deep_delete_to_the_selected_emby(self) -> None:
        """多选保留全部配置，按来源查询，无法确认来源时不删除"""
        for version in (2, 3):
            with self.subTest(version=version):
                plugin, namespace, helper = self._load_plugin(version)
                servers = {
                    name: SimpleNamespace(
                        instance=Mock(get_user=Mock(return_value=f"{name}-user")),
                        config=SimpleNamespace(config={"host": f"{name}:8096", "apikey": f"{name}-key"}),
                    )
                    for name in ("alpha", "beta")
                }
                helper.get_services.return_value = servers
                helper.get_service.side_effect = lambda name, type_filter: servers.get(name)
                bus = namespace["eventmanager"]
                bus.send_event.side_effect = lambda _, data: plugin.sync_del_by_plugin(
                    SimpleNamespace(event_data=data)
                )
                webhook = plugin.emby_webhook if version == 2 else plugin.emby_webhook_api
                message = {
                    "Event": "strmassistant.deep.delete",
                    "Item": {
                        "Type": "Episode",
                        "SeriesId": "123",
                        "Path": "/library/file.mkv",
                        "Name": "Test",
                        "IndexNumber": 1,
                        "ParentIndexNumber": 1,
                    },
                }

                async def body() -> bytes:
                    return json.dumps(message).encode("utf-8")

                def send(server: Optional[str] = None, token: Optional[str] = "token") -> SimpleNamespace:
                    params = {} if token is None else {"apikey": token}
                    if server is not None:
                        params["server"] = server
                    request = SimpleNamespace(
                        query_params=params, headers={"content-type": "application/json"}, body=body
                    )
                    return asyncio.run(webhook(request))

                config = {"enabled": True, "local_library_path": "/library#/mapped"}
                plugin.init_plugin({**config, "mediaservers": ["alpha", "beta"]})
                self.assertEqual(plugin.update_config.call_args.args[0]["mediaservers"], ["alpha", "beta"])
                for server in (None, "unknown", ""):
                    self.assertFalse(send(server).success)
                if version == 3:
                    self.assertFalse(send("beta", token=None).success)
                bus.send_event.assert_not_called()
                build_event = plugin._SaMediaSyncDelMulti__build_webhook_event
                plugin.sync_del_by_plugin(SimpleNamespace(event_data=build_event(dict(message))))
                plugin._SaMediaSyncDelMulti__sync_del.assert_not_called()

                for server in ("beta", "alpha"):
                    self.assertTrue(send(server).success)
                    req = namespace["RequestUtils"].return_value
                    req.get_res.assert_called_with(
                        f"http://{server}:8096/emby/Users/{server}-user/Items/123?api_key={server}-key"
                    )
                self.assertEqual(plugin._SaMediaSyncDelMulti__sync_del.call_count, 2)

                servers.pop("alpha")
                req.get_res.reset_mock()
                self.assertTrue(send("alpha").success)
                req.get_res.assert_not_called()
                helper.get_service.assert_called_with(name="alpha", type_filter="emby")
                self.assertEqual(plugin._SaMediaSyncDelMulti__sync_del.call_count, 2)

                plugin.init_plugin({**config, "mediaservers": ["beta"]})
                self.assertFalse(send("alpha").success)
                self.assertTrue(send().success)
                helper.get_service.assert_called_with(name="beta", type_filter="emby")
                self.assertEqual(plugin._SaMediaSyncDelMulti__sync_del.call_count, 3)


if __name__ == "__main__":
    unittest.main()
