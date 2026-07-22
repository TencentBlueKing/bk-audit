# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from services.web.entry.handler.entry import EntryHandler


class TestAgentAuthEntryConfig(SimpleTestCase):
    @staticmethod
    def _request():
        return SimpleNamespace(user=SimpleNamespace(username="admin"))

    @staticmethod
    def _get_global_meta_config(configs):
        def _get(config_key, *args, **kwargs):
            return configs.get(config_key, kwargs.get("default"))

        return _get

    @mock.patch("services.web.entry.handler.entry.resource.permission.check_permission", return_value={})
    @mock.patch("services.web.entry.handler.entry.GlobalMetaConfig.get")
    def test_entry_projects_enabled_agent_ping_config(self, mock_get, _mock_check_permission):
        expected = {
            "agents": [
                {
                    "code": "audit-risk-agent",
                    "enabled": True,
                    "ping_url": "https://agent.example.woa.com/ping/",
                }
            ]
        }
        raw = {
            "agents": [
                {
                    **expected["agents"][0],
                    "token": "must-not-leak",
                }
            ]
        }
        mock_get.side_effect = self._get_global_meta_config({"agent_auth": raw})

        data = EntryHandler.entry(self._request())

        self.assertEqual(data["agent_auth"], expected)
        self.assertNotIn("token", data["agent_auth"]["agents"][0])

    @mock.patch("services.web.entry.handler.entry.resource.permission.check_permission", return_value={})
    @mock.patch("services.web.entry.handler.entry.GlobalMetaConfig.get")
    def test_entry_returns_empty_agents_for_invalid_config(self, mock_get, _mock_check_permission):
        mock_get.side_effect = self._get_global_meta_config({"agent_auth": {"agents": [{"code": "x"}]}})

        data = EntryHandler.entry(self._request())

        self.assertEqual(data["agent_auth"], {"agents": []})
